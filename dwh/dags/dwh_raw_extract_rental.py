"""
DAG A: dwh_raw_extract_rental
Извлекает данные из db-rental в raw_rental.* (truncate + insert)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from psycopg2.extras import execute_values

from airflow import DAG
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator


DWH_CONN_ID = "dwh_db"
RENTAL_CONN_ID = "rental_db"
SQL_DIR = "/opt/airflow/sql"

# Таблицы для загрузки из rental
RAW_RENTAL_TABLES = [
    {"source_table": "quotes", "target_table": "quotes"},
    {"source_table": "rentals", "target_table": "rentals"},
    {"source_table": "idempotency_keys", "target_table": "idempotency_keys"},
]


def _fetch_columns(pg_hook: PostgresHook, table: str, schema: str = "public") -> list[str]:
    """Получить список колонок таблицы."""
    sql = '''
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    '''
    with pg_hook.get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (schema, table))
        return [r[0] for r in cur.fetchall()]


def _truncate_and_load(
    source_conn_id: str,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    chunk_size: int = 20_000,
) -> dict:
    """Full-load репликация: TRUNCATE target и загрузка всех строк из source."""
    src = PostgresHook(postgres_conn_id=source_conn_id)
    dwh = PostgresHook(postgres_conn_id=DWH_CONN_ID)

    src_cols = _fetch_columns(src, source_table, schema=source_schema)
    tgt_cols = _fetch_columns(dwh, target_table, schema=target_schema)

    # Загружаем только пересекающиеся колонки
    common_cols = [c for c in src_cols if c in tgt_cols and not c.startswith("_")]
    if not common_cols:
        raise ValueError(
            f"No common columns between source {source_schema}.{source_table} "
            f"and target {target_schema}.{target_table}"
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


default_args = {
    "owner": "student",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="dwh_raw_extract_rental",
    start_date=datetime(2025, 1, 1),
    schedule=None,  # Запускается мастер-DAG-ом
    catchup=False,
    template_searchpath=[SQL_DIR],
    default_args=default_args,
    tags=["dwh", "raw", "rental"],
    doc_md="""
    ## DAG A: dwh_raw_extract_rental
    
    Извлекает данные из db-rental в слой raw_rental:
    - raw_rental.quotes
    - raw_rental.rentals
    - raw_rental.idempotency_keys
    
    Использует full-load стратегию (truncate + insert).
    """,
) as dag:

    # Bootstrap: создание схем и RAW таблиц
    bootstrap_schemas = PostgresOperator(
        task_id="bootstrap_schemas",
        postgres_conn_id=DWH_CONN_ID,
        sql="00_schemas.sql",
    )

    bootstrap_raw = PostgresOperator(
        task_id="bootstrap_raw",
        postgres_conn_id=DWH_CONN_ID,
        sql="01_raw.sql",
    )

    @task(task_id="load_raw_rental")
    def load_raw_rental():
        """Загрузка данных из rental в raw_rental.*"""
        results = []
        for cfg in RAW_RENTAL_TABLES:
            results.append(
                _truncate_and_load(
                    source_conn_id=RENTAL_CONN_ID,
                    source_schema="public",
                    source_table=cfg["source_table"],
                    target_schema="raw_rental",
                    target_table=cfg["target_table"],
                )
            )
        return results

    bootstrap_schemas >> bootstrap_raw >> load_raw_rental()


