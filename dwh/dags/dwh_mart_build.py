"""
DAG D: dwh_mart_build
Строит витрины MART из CORE данных, включая mart.kpi_daily с 6 KPI.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator


DWH_CONN_ID = "dwh_db"
SQL_DIR = "/opt/airflow/sql"
ARTIFACTS_DIR = "/opt/airflow/artifacts"

default_args = {
    "owner": "student",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}


def _export_table_to_csv(table_fqn: str, out_path: str) -> None:
    """Экспорт таблицы в CSV файл."""
    dwh = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with dwh.get_conn() as conn, conn.cursor() as cur, open(out_path, "w", encoding="utf-8") as f:
        cur.copy_expert(f"COPY (SELECT * FROM {table_fqn}) TO STDOUT WITH CSV HEADER", f)


with DAG(
    dag_id="dwh_mart_build",
    start_date=datetime(2025, 1, 1),
    schedule=None,  # Запускается мастер-DAG-ом
    catchup=False,
    template_searchpath=[SQL_DIR],
    default_args=default_args,
    tags=["dwh", "mart"],
    doc_md="""
    ## DAG D: dwh_mart_build
    
    Строит витрины MART из CORE данных:
    - mart.fct_rentals — факты по арендам
    - mart.fct_payments — факты по платежам
    - mart.kpi_daily — ежедневные KPI (6 метрик):
      1. quotes_cnt — количество квот
      2. rentals_started_cnt — начатых аренд
      3. rentals_finished_cnt — завершённых аренд
      4. payments_attempts_cnt — попыток оплаты
      5. payments_success_cnt — успешных оплат
      6. revenue_amount — выручка
      + avg_rental_duration_min — средняя длительность аренды
    """,
) as dag:

    build_mart = PostgresOperator(
        task_id="build_mart",
        postgres_conn_id=DWH_CONN_ID,
        sql="03_mart.sql",
    )

    @task(task_id="export_artifacts")
    def export_artifacts():
        """Экспорт витрин в CSV для артефактов."""
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_files = []
        for table in ["mart.kpi_daily", "mart.fct_rentals", "mart.fct_payments"]:
            out_path = os.path.join(ARTIFACTS_DIR, f"{table.replace('.', '_')}_{ts}.csv")
            _export_table_to_csv(table, out_path)
            out_files.append(out_path)
        return out_files

    build_mart >> export_artifacts()


