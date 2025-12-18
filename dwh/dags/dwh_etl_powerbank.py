from __future__ import annotations

import os
from datetime import datetime, timedelta

from psycopg2.extras import execute_values

from airflow import DAG
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator


DWH_CONN_ID = "dwh_db"
RENTAL_CONN_ID = "rental_db"
BILLING_CONN_ID = "billing_db"

SQL_DIR = "/opt/airflow/sql"
ARTIFACTS_DIR = "/opt/airflow/artifacts"

# Tables we replicate into RAW. If your source uses other names/schemas, change here.
RAW_LOAD_CONFIG = [
    # rental service
    {"source_conn_id": RENTAL_CONN_ID, "source_schema": "public", "source_table": "quotes", "target_schema": "raw_rental", "target_table": "quotes"},
    {"source_conn_id": RENTAL_CONN_ID, "source_schema": "public", "source_table": "rentals", "target_schema": "raw_rental", "target_table": "rentals"},
    {"source_conn_id": RENTAL_CONN_ID, "source_schema": "public", "source_table": "idempotency_keys", "target_schema": "raw_rental", "target_table": "idempotency_keys"},
    # billing service
    {"source_conn_id": BILLING_CONN_ID, "source_schema": "public", "source_table": "debts", "target_schema": "raw_billing", "target_table": "debts"},
    {"source_conn_id": BILLING_CONN_ID, "source_schema": "public", "source_table": "payment_attempts", "target_schema": "raw_billing", "target_table": "payment_attempts"},
]


def _fetch_columns(pg_hook: PostgresHook, table: str, schema: str = "public") -> list[str]:
    sql = '''
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    '''
    with pg_hook.get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (schema, table))
        return [r[0] for r in cur.fetchall()]


def _truncate_and_load_full(
    source_conn_id: str,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    chunk_size: int = 20_000,
) -> dict:
    # Full-load replication: TRUNCATE target and load all rows from source.
    # Deterministic and simple for homework data volumes.

    src = PostgresHook(postgres_conn_id=source_conn_id)
    dwh = PostgresHook(postgres_conn_id=DWH_CONN_ID)

    src_cols = _fetch_columns(src, source_table, schema=source_schema)
    tgt_cols = _fetch_columns(dwh, target_table, schema=target_schema)

    # Load only intersection to avoid failures if your DDL differs.
    common_cols = [c for c in src_cols if c in tgt_cols and not c.startswith("_")]
    if not common_cols:
        raise ValueError(
            f"No common columns between source {source_schema}.{source_table} and target {target_schema}.{target_table}"
        )

    select_sql = f'SELECT {", ".join(common_cols)} FROM {source_schema}.{source_table}'
    insert_cols_sql = ", ".join(common_cols) + (", _ingested_at" if "_ingested_at" in tgt_cols else "")

    inserted = 0
    with src.get_conn() as sconn, dwh.get_conn() as dconn:
        dconn.autocommit = False

        # 1) truncate RAW table
        with dconn.cursor() as dcur:
            dcur.execute(f"TRUNCATE TABLE {target_schema}.{target_table}")
        dconn.commit()

        # 2) stream rows from source
        scur = sconn.cursor(name=f"sscur_{source_table}")
        try:
            scur.itersize = chunk_size
            scur.execute(select_sql)

            with dconn.cursor() as dcur:
                while True:
                    rows = scur.fetchmany(chunk_size)
                    if not rows:
                        break

                    if "_ingested_at" in tgt_cols:
                        execute_values(
                            dcur,
                            f"INSERT INTO {target_schema}.{target_table} ({insert_cols_sql}) VALUES %s",
                            [tuple(r) for r in rows],
                            template="(" + ", ".join(["%s"] * len(common_cols)) + ", now())",
                            page_size=5000,
                        )
                    else:
                        execute_values(
                            dcur,
                            f"INSERT INTO {target_schema}.{target_table} ({insert_cols_sql}) VALUES %s",
                            [tuple(r) for r in rows],
                            template="(" + ", ".join(["%s"] * len(common_cols)) + ")",
                            page_size=5000,
                        )
                    inserted += len(rows)

            dconn.commit()
        finally:
            scur.close()

    return {
        "source": f"{source_schema}.{source_table}",
        "target": f"{target_schema}.{target_table}",
        "rows_loaded": inserted,
        "columns": common_cols,
    }


def _export_table_to_csv(table_fqn: str, out_path: str) -> None:
    dwh = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with dwh.get_conn() as conn, conn.cursor() as cur, open(out_path, "w", encoding="utf-8") as f:
        cur.copy_expert(f"COPY (SELECT * FROM {table_fqn}) TO STDOUT WITH CSV HEADER", f)


default_args = {"owner": "student", "retries": 2, "retry_delay": timedelta(minutes=1)}

with DAG(
    dag_id="dwh_powerbank_etl",
    start_date=datetime(2025, 1, 1),
    schedule="@daily",
    catchup=False,
    template_searchpath=[SQL_DIR],
    default_args=default_args,
    tags=["dwh", "powerbank"],
) as dag:

    # 1) Bootstrap DWH structure
    dwh_bootstrap = PostgresOperator(
        task_id="dwh_bootstrap",
        postgres_conn_id=DWH_CONN_ID,
        sql=[
            "00_schemas.sql",
            "04_meta.sql",
            "01_raw.sql",
        ],
    )

    # 2) Load RAW from sources (full load for each table)
    @task(task_id="load_raw")
    def load_raw():
        results = []
        for cfg in RAW_LOAD_CONFIG:
            results.append(
                _truncate_and_load_full(
                    source_conn_id=cfg["source_conn_id"],
                    source_schema=cfg["source_schema"],
                    source_table=cfg["source_table"],
                    target_schema=cfg["target_schema"],
                    target_table=cfg["target_table"],
                )
            )
        return results

    # 3) Build CORE + MART
    build_core = PostgresOperator(
        task_id="build_core",
        postgres_conn_id=DWH_CONN_ID,
        sql="02_core.sql",
    )

    build_mart = PostgresOperator(
        task_id="build_mart",
        postgres_conn_id=DWH_CONN_ID,
        sql="03_mart.sql",
    )

    # 4) Export artifacts (CSV snapshots)
    @task(task_id="export_artifacts")
    def export_artifacts():
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_files = []
        for table in ["mart.kpi_daily", "mart.fct_rentals", "mart.fct_payments"]:
            out_path = os.path.join(ARTIFACTS_DIR, f"{table.replace('.', '_')}_{ts}.csv")
            _export_table_to_csv(table, out_path)
            out_files.append(out_path)
        return out_files

    dwh_bootstrap >> load_raw() >> build_core >> build_mart >> export_artifacts()
