"""One-time BigQuery setup: create datasets and raw tables with explicit schemas.

Creates the ``raw``, ``staging``, and ``marts`` datasets (names from env vars)
and one raw table per entry in the ingestion dataset registry. Idempotent —
safe to re-run; existing datasets/tables are left untouched.

Usage:
    python scripts/setup_bigquery.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.api_core.exceptions import Conflict
from google.cloud import bigquery

from ingestion.config import DATASETS, get_env

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("setup_bigquery")


def create_dataset(client: bigquery.Client, dataset_id: str, location: str) -> None:
    """Create a BigQuery dataset if it does not already exist.

    Args:
        client: Authenticated BigQuery client.
        dataset_id: Fully qualified ``project.dataset`` id.
        location: BigQuery location (e.g. "US").
    """
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = location
    try:
        client.create_dataset(dataset)
        logger.info("Created dataset %s", dataset_id)
    except Conflict:
        logger.info("Dataset %s already exists", dataset_id)


def create_raw_tables(client: bigquery.Client, project: str, raw_dataset: str) -> None:
    """Create every raw table from the ingestion registry with explicit schema.

    Args:
        client: Authenticated BigQuery client.
        project: GCP project id.
        raw_dataset: Name of the raw dataset.
    """
    for config in DATASETS.values():
        schema = [
            bigquery.SchemaField(name, bq_type)
            for name, bq_type in config.columns.items()
        ] + [bigquery.SchemaField("_loaded_at", "TIMESTAMP")]
        table = bigquery.Table(f"{project}.{raw_dataset}.{config.table}", schema=schema)
        try:
            client.create_table(table)
            logger.info("Created table %s.%s", raw_dataset, config.table)
        except Conflict:
            logger.info("Table %s.%s already exists", raw_dataset, config.table)


def main() -> int:
    """Create all datasets and raw tables."""
    project = get_env("GCP_PROJECT_ID")
    location = get_env("BQ_LOCATION", "US")
    client = bigquery.Client(project=project)

    for env_name, default in (
        ("BQ_DATASET_RAW", "raw"),
        ("BQ_DATASET_STAGING", "staging"),
        ("BQ_DATASET_MARTS", "marts"),
    ):
        create_dataset(client, f"{project}.{get_env(env_name, default)}", location)

    create_raw_tables(client, project, get_env("BQ_DATASET_RAW", "raw"))
    logger.info("BigQuery setup complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
