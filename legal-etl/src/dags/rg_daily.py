from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.workers.fetch_worker import enqueue_new_items


def trigger_rg():
    # Placeholder: RG connector will enqueue jobs once implemented.
    enqueue_new_items()


with DAG(
    dag_id="rg_daily",
    schedule="5 6,17 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"owner": "data"},
) as dag:
    PythonOperator(task_id="enqueue_rg", python_callable=trigger_rg)
