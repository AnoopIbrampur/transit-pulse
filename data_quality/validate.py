"""Validate raw MTA BigQuery tables against Great Expectations suites.

Each configured raw table is loaded into a pandas DataFrame from BigQuery and
checked against its suite (defined in :mod:`great_expectations.suites`) using an
ephemeral GE context. Runs after ingestion and before dbt in the Airflow DAG;
:func:`main` exits non-zero if any suite fails so the DAG halts.

Usage:
    python -m great_expectations.validate                 # all configured tables
    python -m great_expectations.validate --tables terminal_otp
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import great_expectations as gx
import pandas as pd
from great_expectations import expectations as gxe

from data_quality.suites import SUITES  # noqa: E402  (after sys.path insert)
from ingestion.config import get_env  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("ge_validate")

# Map expectation_type strings to GE 1.x expectation classes.
_EXPECTATION_CLASSES = {
    "expect_column_values_to_not_be_null": gxe.ExpectColumnValuesToNotBeNull,
    "expect_column_values_to_be_between": gxe.ExpectColumnValuesToBeBetween,
    "expect_column_values_to_be_in_set": gxe.ExpectColumnValuesToBeInSet,
    "expect_table_row_count_to_be_between": gxe.ExpectTableRowCountToBeBetween,
    "expect_column_pair_values_a_to_be_greater_than_b": (
        gxe.ExpectColumnPairValuesAToBeGreaterThanB
    ),
}


def load_raw_table(table: str) -> pd.DataFrame:
    """Load a raw table from BigQuery into a DataFrame.

    Args:
        table: Raw table name (also the suite key).

    Returns:
        The full table as a pandas DataFrame.
    """
    from google.cloud import bigquery

    project = get_env("GCP_PROJECT_ID")
    raw = get_env("BQ_DATASET_RAW", "raw")
    client = bigquery.Client(project=project)
    frame = client.query(f"SELECT * FROM `{project}.{raw}.{table}`").to_dataframe()

    # Normalize datetime dtypes so cross-column comparisons work: BigQuery DATE
    # arrives as tz-naive "dbdate" while TIMESTAMP arrives as tz-aware
    # datetime64[UTC]; pandas refuses to compare the two. Coerce every temporal
    # column to tz-naive datetime64[ns].
    for column in frame.columns:
        dtype_str = str(frame[column].dtype)
        if dtype_str == "dbdate" or "datetime64" in dtype_str:
            series = pd.to_datetime(frame[column], errors="coerce")
            if getattr(series.dt, "tz", None) is not None:
                series = series.dt.tz_localize(None)
            frame[column] = series

    logger.info("Loaded %d rows from %s.%s", len(frame), raw, table)
    return frame


def build_suite(name: str) -> gx.ExpectationSuite:
    """Construct a GE ExpectationSuite from the declarative SUITES registry.

    Args:
        name: Suite/table name present in SUITES.

    Returns:
        A populated ExpectationSuite.

    Raises:
        KeyError: If the suite name or an expectation type is unknown.
    """
    suite = gx.ExpectationSuite(name=f"{name}_suite")
    for exp_type, kwargs in SUITES[name]:
        suite.add_expectation(_EXPECTATION_CLASSES[exp_type](**kwargs))
    return suite


def validate_table(context: "gx.data_context.AbstractDataContext", table: str) -> bool:
    """Validate one raw table against its suite.

    Args:
        context: An ephemeral GE data context.
        table: Raw table name / suite key.

    Returns:
        True if all expectations pass, False otherwise.
    """
    frame = load_raw_table(table)
    data_source = context.data_sources.add_pandas(f"{table}_src")
    asset = data_source.add_dataframe_asset(name=table)
    batch_def = asset.add_batch_definition_whole_dataframe(f"{table}_batch")
    suite = build_suite(table)

    results = batch_def.get_batch(batch_parameters={"dataframe": frame}).validate(suite)

    if results.success:
        logger.info("✅ %s: all %d expectations passed", table, len(results.results))
    else:
        failed = [
            r.expectation_config.type
            for r in results.results
            if not r.success
        ]
        logger.error("❌ %s: %d expectation(s) FAILED: %s", table, len(failed), failed)
    return bool(results.success)


def main(argv: list[str] | None = None) -> int:
    """Validate all (or selected) raw tables; return 1 if any suite fails."""
    parser = argparse.ArgumentParser(description="Validate raw MTA tables with GE")
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=sorted(SUITES),
        default=sorted(SUITES),
        help="Tables to validate (default: all configured)",
    )
    args = parser.parse_args(argv)

    context = gx.get_context(mode="ephemeral")
    all_passed = True
    for table in args.tables:
        if not validate_table(context, table):
            all_passed = False

    if all_passed:
        logger.info("All data-quality checks passed")
        return 0
    logger.error("Data-quality validation FAILED — halting pipeline")
    return 1


if __name__ == "__main__":
    sys.exit(main())
