from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.workers.fetch_worker import enqueue_new_items


with DAG(
    dag_id="boards_daily",
    schedule="0 10 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"owner": "data"},
) as dag:
    PythonOperator(task_id="enqueue_board_sources", python_callable=enqueue_new_items)
