"""
DAG C: dwh_core_build
Строит CORE слой из RAW данных (upsert/full refresh).
SoT соблюдается: core.debt/core.payment_attempt только из raw_billing.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator


DWH_CONN_ID = "dwh_db"
SQL_DIR = "/opt/airflow/sql"

default_args = {
    "owner": "student",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="dwh_core_build",
    start_date=datetime(2025, 1, 1),
    schedule=None,  # Запускается мастер-DAG-ом
    catchup=False,
    template_searchpath=[SQL_DIR],
    default_args=default_args,
    tags=["dwh", "core"],
    doc_md="""
    ## DAG C: dwh_core_build
    
    Строит CORE слой из RAW данных:
    - core.quotes ← raw_rental.quotes
    - core.rentals ← raw_rental.rentals  
    - core.idempotency_keys ← raw_rental.idempotency_keys
    - core.debts ← raw_billing.debts (SoT = billing)
    - core.payment_attempts ← raw_billing.payment_attempts (SoT = billing)
    
    **Важно**: SoT для долгов и платежей — только billing!
    """,
) as dag:

    build_core = PostgresOperator(
        task_id="build_core",
        postgres_conn_id=DWH_CONN_ID,
        sql="02_core.sql",
    )

    build_core


