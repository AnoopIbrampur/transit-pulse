"""Airflow DAG: transit_pulse_elt.

Daily ELT pipeline for NYC MTA subway data:

    ingest_mta_data → validate_raw_data → dbt_run → dbt_test

The source data is monthly, so the DAG runs daily but is naturally idempotent —
ingestion only appends months newer than what BigQuery already holds, and the
run is a no-op when there is nothing new. Great Expectations validation gates
dbt: if data quality fails, the transform tasks never run.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Container paths (see docker-compose volume mounts). Overridable via env.
PROJECT_ROOT = "/opt/transit_pulse"
DBT_PROJECT_DIR = f"{PROJECT_ROOT}/dbt_transit"

default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # Alerting is configured here to show production intent even if SMTP/Slack
    # are not wired up in local dev.
    "email": ["data-alerts@example.com"],
    "email_on_failure": True,
    "email_on_retry": False,
}


def _run_ingestion() -> None:
    """Run the MTA ingestion for all datasets (PythonOperator callable)."""
    from ingestion.mta_ingest import main as ingest_main

    exit_code = ingest_main([])
    if exit_code != 0:
        raise RuntimeError("MTA ingestion reported failures")


def _run_validation() -> None:
    """Run Great Expectations validation on the raw tables (PythonOperator)."""
    from data_quality.validate import main as validate_main

    exit_code = validate_main([])
    if exit_code != 0:
        raise RuntimeError("Great Expectations validation failed — halting pipeline")


with DAG(
    dag_id="transit_pulse_elt",
    description="Ingest → validate → transform NYC MTA subway performance data",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["mta", "elt", "bigquery", "dbt"],
) as dag:
    ingest_mta_data = PythonOperator(
        task_id="ingest_mta_data",
        python_callable=_run_ingestion,
    )

    validate_raw_data = PythonOperator(
        task_id="validate_raw_data",
        python_callable=_run_validation,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt test --profiles-dir .",
    )

    ingest_mta_data >> validate_raw_data >> dbt_run >> dbt_test
