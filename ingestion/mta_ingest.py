"""Generic SODA → BigQuery ingestion for MTA open datasets.

Driven entirely by the ``DATASETS`` registry in :mod:`ingestion.config`:
pagination, retries with exponential backoff, incremental loading based on the
max date already in BigQuery, natural-key deduplication, and explicit-schema
loads with a ``_loaded_at`` metadata column.

Usage:
    python -m ingestion.mta_ingest                       # all datasets, API mode
    python -m ingestion.mta_ingest --datasets terminal_otp stations
    python -m ingestion.mta_ingest --dry-run             # fetch + report, no BQ
    python -m ingestion.mta_ingest --datasets stations --source local --file stations.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd
import requests

if TYPE_CHECKING:
    from google.cloud import bigquery

from ingestion.config import (
    DATASETS,
    MAX_RETRIES,
    PAGE_SIZE,
    RETRY_BACKOFF_SECONDS,
    SODA_BASE_URL,
    DatasetConfig,
    get_env,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mta_ingest")


def _request_with_retries(url: str, params: dict[str, str]) -> list[dict]:
    """GET a SODA endpoint, retrying on failure with exponential backoff.

    Args:
        url: Full resource URL (e.g. https://data.ny.gov/resource/xxxx-xxxx.json).
        params: SODA query parameters ($limit, $offset, $where, ...).

    Returns:
        Parsed JSON list of row dicts.

    Raises:
        requests.HTTPError: If all retries are exhausted.
    """
    headers: dict[str, str] = {}
    token = get_env("MTA_APP_TOKEN", "")
    if token:
        headers["X-App-Token"] = token

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "Request failed (attempt %d/%d): %s — retrying in %.0fs",
                attempt,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"SODA request failed after {MAX_RETRIES} retries: {last_error}")


def fetch_from_api(dataset: DatasetConfig, since: date | None = None) -> pd.DataFrame:
    """Fetch all rows for a dataset from the SODA API with pagination.

    Args:
        dataset: Registry entry describing the dataset.
        since: If set (and the dataset is incremental), only fetch rows with
            ``date_column`` strictly after this date.

    Returns:
        Raw DataFrame with string-typed columns as returned by Socrata.
    """
    url = f"{SODA_BASE_URL}/{dataset.socrata_id}.json"
    order_by = ",".join(dataset.key_columns)
    frames: list[pd.DataFrame] = []
    offset = 0

    while True:
        params: dict[str, str] = {
            "$limit": str(PAGE_SIZE),
            "$offset": str(offset),
            "$order": order_by,
        }
        if since is not None and dataset.date_column is not None:
            params["$where"] = (
                f"{dataset.date_column} > '{since.isoformat()}T00:00:00.000'"
            )
        rows = _request_with_retries(url, params)
        if not rows:
            break
        frames.append(pd.DataFrame(rows))
        logger.info("%s: fetched %d rows (offset %d)", dataset.name, len(rows), offset)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    if not frames:
        return pd.DataFrame(columns=list(dataset.columns))
    return pd.concat(frames, ignore_index=True)


def fetch_from_local(dataset: DatasetConfig, path: str) -> pd.DataFrame:
    """Load a dataset from a locally downloaded CSV (SODA outage fallback).

    Args:
        dataset: Registry entry describing the dataset.
        path: Path to a CSV exported from data.ny.gov.

    Returns:
        Raw DataFrame; column names are lowercased/underscored to match the
        API field names.
    """
    frame = pd.read_csv(path, dtype=str)
    frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
    logger.info("%s: read %d rows from %s", dataset.name, len(frame), path)
    return frame


def conform_schema(dataset: DatasetConfig, frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce a raw frame to the dataset's declared schema.

    Drops unexpected columns, adds missing ones as nulls, casts types, and
    deduplicates on the natural key.

    Args:
        dataset: Registry entry with the target schema.
        frame: Raw DataFrame from the API or a local CSV.

    Returns:
        A schema-conformed, deduplicated DataFrame.
    """
    out = pd.DataFrame(index=frame.index)
    for column, bq_type in dataset.columns.items():
        series = frame[column] if column in frame.columns else pd.Series(
            [None] * len(frame), index=frame.index
        )
        if bq_type == "DATE":
            out[column] = pd.to_datetime(series, errors="coerce").dt.date
        elif bq_type in ("FLOAT64", "INT64"):
            numeric = pd.to_numeric(series, errors="coerce")
            out[column] = numeric.astype("Int64") if bq_type == "INT64" else numeric
        else:
            out[column] = series.astype("string")

    before = len(out)
    out = out.drop_duplicates(subset=list(dataset.key_columns), keep="first")
    dropped = before - len(out)
    if dropped:
        logger.info("%s: dropped %d duplicate rows on key %s", dataset.name, dropped, dataset.key_columns)
    return out.reset_index(drop=True)


def get_max_loaded_date(client: "bigquery.Client", dataset: DatasetConfig) -> date | None:
    """Return the max value of the incremental date column already in BigQuery.

    Args:
        client: Authenticated BigQuery client.
        dataset: Registry entry (must have a date_column).

    Returns:
        The max date, or None if the table is empty or missing.
    """
    from google.api_core.exceptions import NotFound

    project = get_env("GCP_PROJECT_ID")
    raw = get_env("BQ_DATASET_RAW", "raw")
    table_ref = f"{project}.{raw}.{dataset.table}"
    query = f"SELECT MAX({dataset.date_column}) AS max_date FROM `{table_ref}`"
    try:
        result = list(client.query(query).result())
    except NotFound:
        logger.info("%s: table %s not found — full load", dataset.name, table_ref)
        return None
    max_date = result[0]["max_date"] if result else None
    logger.info("%s: max loaded %s = %s", dataset.name, dataset.date_column, max_date)
    return max_date


def load_to_bigquery(
    client: "bigquery.Client", dataset: DatasetConfig, frame: pd.DataFrame
) -> int:
    """Load a conformed DataFrame into the raw BigQuery table.

    Incremental datasets are appended (WRITE_APPEND); dimension datasets
    (date_column is None) are fully replaced (WRITE_TRUNCATE). A ``_loaded_at``
    UTC timestamp column is stamped on every row.

    Args:
        client: Authenticated BigQuery client.
        dataset: Registry entry.
        frame: Schema-conformed rows to load.

    Returns:
        Number of rows loaded.
    """
    from google.cloud import bigquery

    project = get_env("GCP_PROJECT_ID")
    raw = get_env("BQ_DATASET_RAW", "raw")
    table_ref = f"{project}.{raw}.{dataset.table}"

    frame = frame.copy()
    frame["_loaded_at"] = datetime.now(timezone.utc)

    schema = [
        bigquery.SchemaField(name, bq_type)
        for name, bq_type in dataset.columns.items()
    ] + [bigquery.SchemaField("_loaded_at", "TIMESTAMP")]

    disposition = (
        bigquery.WriteDisposition.WRITE_TRUNCATE
        if dataset.date_column is None
        else bigquery.WriteDisposition.WRITE_APPEND
    )
    job_config = bigquery.LoadJobConfig(schema=schema, write_disposition=disposition)
    job = client.load_table_from_dataframe(frame, table_ref, job_config=job_config)
    job.result()
    logger.info("%s: loaded %d rows into %s (%s)", dataset.name, len(frame), table_ref, disposition)
    return len(frame)


def ingest_dataset(
    dataset: DatasetConfig,
    source: str = "api",
    local_file: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run the full ingest pipeline for one dataset.

    Args:
        dataset: Registry entry to ingest.
        source: "api" (SODA) or "local" (CSV fallback).
        local_file: CSV path, required when source == "local".
        dry_run: If True, fetch and conform but skip BigQuery entirely.

    Returns:
        Stats dict: rows_fetched, rows_loaded, rows_skipped.
    """
    since: date | None = None
    client = None
    if not dry_run:
        from google.cloud import bigquery

        client = bigquery.Client(project=get_env("GCP_PROJECT_ID"))
        if dataset.date_column is not None:
            since = get_max_loaded_date(client, dataset)

    if source == "local":
        if not local_file:
            raise ValueError("--file is required with --source local")
        raw_frame = fetch_from_local(dataset, local_file)
        if since is not None and dataset.date_column is not None:
            date_col = pd.to_datetime(raw_frame[dataset.date_column], errors="coerce").dt.date
            raw_frame = raw_frame[date_col > since]
    else:
        raw_frame = fetch_from_api(dataset, since=since)

    fetched = len(raw_frame)
    conformed = conform_schema(dataset, raw_frame)
    skipped = fetched - len(conformed)

    loaded = 0
    if dry_run:
        logger.info("%s: DRY RUN — %d rows ready, not loading", dataset.name, len(conformed))
    elif conformed.empty:
        logger.info("%s: no new rows to load", dataset.name)
    else:
        loaded = load_to_bigquery(client, dataset, conformed)

    stats = {"rows_fetched": fetched, "rows_loaded": loaded, "rows_skipped": skipped}
    logger.info("%s: done %s", dataset.name, stats)
    return stats


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ingest one, several, or all registered datasets."""
    parser = argparse.ArgumentParser(description="Ingest MTA open data into BigQuery")
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=sorted(DATASETS),
        default=sorted(DATASETS),
        help="Datasets to ingest (default: all)",
    )
    parser.add_argument("--source", choices=["api", "local"], default="api")
    parser.add_argument("--file", help="CSV path when --source local (single dataset only)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not load to BigQuery")
    args = parser.parse_args(argv)

    if args.source == "local" and len(args.datasets) != 1:
        parser.error("--source local requires exactly one --datasets entry")

    failures = 0
    for name in args.datasets:
        try:
            ingest_dataset(DATASETS[name], source=args.source, local_file=args.file, dry_run=args.dry_run)
        except Exception:
            logger.exception("%s: ingestion failed", name)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
