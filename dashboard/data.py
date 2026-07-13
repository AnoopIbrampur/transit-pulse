"""Cached BigQuery data-access layer for the Streamlit dashboard.

Authentication works two ways with no code change:

* **Local dev** — uses ``GOOGLE_APPLICATION_CREDENTIALS`` (service-account key)
  and ``GCP_PROJECT_ID`` from the environment / ``.env``.
* **Streamlit Community Cloud** — reads the service account from
  ``st.secrets["gcp_service_account"]`` and the project from
  ``st.secrets["gcp_project_id"]``.

Every query is wrapped in ``@st.cache_data(ttl=3600)`` so the dashboard loads
in well under five seconds and stays within the BigQuery free tier.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

# Load .env from the project root explicitly — the Streamlit process may not run
# with the repo as its working directory.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_MARTS_SCHEMA = os.environ.get("BQ_DATASET_MARTS", "marts")


@st.cache_resource(show_spinner=False)
def get_client() -> bigquery.Client:
    """Return a cached BigQuery client, auth resolved per environment.

    Returns:
        An authenticated BigQuery client.
    """
    # st.secrets raises when no secrets.toml exists (local dev) — treat as absent.
    try:
        has_secret = "gcp_service_account" in st.secrets
    except Exception:  # noqa: BLE001 — no secrets.toml locally
        has_secret = False

    if has_secret:
        credentials = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"])
        )
        project = st.secrets.get("gcp_project_id", credentials.project_id)
        return bigquery.Client(credentials=credentials, project=project)
    # Local: GOOGLE_APPLICATION_CREDENTIALS + GCP_PROJECT_ID from env.
    return bigquery.Client(project=os.environ["GCP_PROJECT_ID"])


def _project() -> str:
    """Return the active GCP project id."""
    return get_client().project


@st.cache_data(ttl=3600, show_spinner="Querying BigQuery…")
def run_query(sql: str) -> pd.DataFrame:
    """Run a SQL query against BigQuery and return a DataFrame (cached 1h).

    Args:
        sql: A fully-qualified SQL string.

    Returns:
        Query results as a pandas DataFrame.
    """
    return get_client().query(sql).to_dataframe()


def _marts(table: str) -> str:
    """Return the fully-qualified marts table reference."""
    return f"`{_project()}.{_MARTS_SCHEMA}.{table}`"


@st.cache_data(ttl=3600)
def load_line_reliability() -> pd.DataFrame:
    """Load the full line-reliability mart, oldest→newest."""
    return run_query(f"SELECT * FROM {_marts('mart_line_reliability')} ORDER BY period")


@st.cache_data(ttl=3600)
def load_delay_analysis() -> pd.DataFrame:
    """Load the full delay-analysis mart, oldest→newest."""
    return run_query(f"SELECT * FROM {_marts('mart_delay_analysis')} ORDER BY period")


@st.cache_data(ttl=3600)
def load_time_trends() -> pd.DataFrame:
    """Load the full time-trends mart, oldest→newest."""
    return run_query(f"SELECT * FROM {_marts('mart_time_trends')} ORDER BY period")


@st.cache_data(ttl=3600)
def load_station_performance() -> pd.DataFrame:
    """Load the station-performance map feed."""
    return run_query(f"SELECT * FROM {_marts('mart_station_performance')}")


@st.cache_data(ttl=3600)
def load_delay_causes() -> pd.DataFrame:
    """Load the delay root-cause mart, oldest→newest."""
    return run_query(f"SELECT * FROM {_marts('mart_delay_causes')} ORDER BY period")


@st.cache_data(ttl=3600)
def load_ridership_recovery() -> pd.DataFrame:
    """Load the ridership-recovery-by-station mart."""
    return run_query(f"SELECT * FROM {_marts('mart_ridership_recovery')}")


@st.cache_data(ttl=3600)
def load_analysis_output(name: str) -> dict:
    """Load a precomputed analysis result JSON from analysis/outputs.

    Args:
        name: File stem (e.g. "drivers", "forecast", "anomalies", "recovery").

    Returns:
        The parsed JSON as a dict, or {} if the file is missing.
    """
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "analysis" / "outputs" / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def available_lines() -> list[str]:
    """Return the sorted list of line names present in the reliability mart."""
    frame = load_line_reliability()
    return sorted(frame["line_name"].dropna().unique().tolist())


def filter_by_lines_and_dates(
    frame: pd.DataFrame,
    lines: list[str],
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None,
    line_col: str = "line_name",
    date_col: str = "period",
) -> pd.DataFrame:
    """Apply the global sidebar line + date filters to a mart DataFrame.

    Args:
        frame: Source DataFrame.
        lines: Selected line names (empty means all).
        date_range: (start, end) inclusive, or None for no date filter.
        line_col: Name of the line column.
        date_col: Name of the date column.

    Returns:
        The filtered DataFrame.
    """
    out = frame
    if lines:
        out = out[out[line_col].isin(lines)]
    if date_range and date_col in out.columns:
        start, end = date_range
        dates = pd.to_datetime(out[date_col])
        out = out[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    return out


# Shared color map for reliability tiers — canonical values live in theme.py.
from theme import TIER_COLORS  # noqa: E402, F401  (re-export for pages/map)
