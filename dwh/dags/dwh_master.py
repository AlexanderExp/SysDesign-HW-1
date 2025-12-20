"""
Master DAG: dwh_master
Оркестрирует все ETL DAG-и в правильном порядке.
Запуск одного этого DAG-а даёт полный результат ETL.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor


default_args = {
    "owner": "student",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="dwh_master",
    start_date=datetime(2025, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["dwh", "master", "orchestration"],
    doc_md="""
    ## Master DAG: dwh_master
    
    Оркестрирует полный ETL процесс DWH в правильном порядке:
    
    1. **dwh_raw_extract_rental** (DAG A) — загрузка из rental в raw_rental
    2. **dwh_raw_extract_billing** (DAG B) — загрузка из billing в raw_billing
       (выполняются параллельно)
    3. **dwh_core_build** (DAG C) — построение CORE слоя
    4. **dwh_mart_build** (DAG D) — построение витрин MART + экспорт CSV
    
    ### Использование
    
    Для полного прогона ETL достаточно запустить только этот DAG:
    ```
    airflow dags trigger dwh_master
    ```
    
    ### SoT (Source of Truth)
    
    - core.rentals, core.quotes, core.idempotency_keys ← rental
    - core.debts, core.payment_attempts ← billing (SoT!)
    """,
) as dag:

    # Запуск RAW extract DAG-ов (параллельно)
    trigger_raw_rental = TriggerDagRunOperator(
        task_id="trigger_raw_rental",
        trigger_dag_id="dwh_raw_extract_rental",
        wait_for_completion=True,
        poke_interval=10,
        allowed_states=["success"],
        failed_states=["failed"],
    )

    trigger_raw_billing = TriggerDagRunOperator(
        task_id="trigger_raw_billing",
        trigger_dag_id="dwh_raw_extract_billing",
        wait_for_completion=True,
        poke_interval=10,
        allowed_states=["success"],
        failed_states=["failed"],
    )

    # Запуск CORE build DAG (после завершения RAW)
    trigger_core_build = TriggerDagRunOperator(
        task_id="trigger_core_build",
        trigger_dag_id="dwh_core_build",
        wait_for_completion=True,
        poke_interval=10,
        allowed_states=["success"],
        failed_states=["failed"],
    )

    # Запуск MART build DAG (после завершения CORE)
    trigger_mart_build = TriggerDagRunOperator(
        task_id="trigger_mart_build",
        trigger_dag_id="dwh_mart_build",
        wait_for_completion=True,
        poke_interval=10,
        allowed_states=["success"],
        failed_states=["failed"],
    )

    # Зависимости: RAW параллельно → CORE → MART
    [trigger_raw_rental, trigger_raw_billing] >> trigger_core_build >> trigger_mart_build


