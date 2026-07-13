"""Shared BigQuery access for the analysis modules.

Thin helpers that pull marts into pandas DataFrames. Kept separate from the
dashboard's data layer because these run headless (no Streamlit) in scripts and
notebooks.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from ingestion.config import get_env

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logger = logging.getLogger("analysis")

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


def query(sql: str) -> pd.DataFrame:
    """Run SQL against BigQuery and return a DataFrame.

    Args:
        sql: A fully-qualified SQL string.

    Returns:
        The query result as a pandas DataFrame.
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=get_env("GCP_PROJECT_ID"))
    return client.query(sql).to_dataframe()


def marts(table: str) -> str:
    """Return a fully-qualified marts table reference for use in SQL."""
    project = get_env("GCP_PROJECT_ID")
    schema = get_env("BQ_DATASET_MARTS", "marts")
    return f"`{project}.{schema}.{table}`"
