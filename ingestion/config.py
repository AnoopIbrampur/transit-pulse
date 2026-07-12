"""Dataset registry and environment configuration for MTA ingestion.

This module is the single source of truth for which Socrata datasets feed the
raw BigQuery layer: their IDs, explicit schemas, natural keys, and incremental
strategy. ``mta_ingest.py`` and ``scripts/setup_bigquery.py`` both read from it.

Dataset IDs were verified live against data.ny.gov on 2026-07-12.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

SODA_BASE_URL = "https://data.ny.gov/resource"
PAGE_SIZE = 1000
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0  # doubles each retry: 2s, 4s, 8s


def get_env(name: str, default: str | None = None) -> str:
    """Return an environment variable, raising a clear error if missing.

    Args:
        name: Environment variable name.
        default: Fallback value; if None the variable is required.

    Raises:
        RuntimeError: If the variable is required but unset.
    """
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(
            f"Required environment variable {name!r} is not set. "
            "Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration for one Socrata dataset feeding one raw BigQuery table.

    Attributes:
        name: Short registry key, also used as the CLI dataset name.
        socrata_id: The 4x4 Socrata dataset identifier on data.ny.gov.
        table: Target table name inside the raw BigQuery dataset.
        columns: Ordered mapping of column name -> BigQuery type
            (DATE / STRING / INT64 / FLOAT64 / BOOL). Only these columns are
            kept from the API response; everything else is dropped.
        key_columns: Natural key used to deduplicate rows before loading.
        date_column: Column used for incremental loads (only rows newer than
            the max already in BigQuery are appended). None means the dataset
            is a dimension and gets fully refreshed (WRITE_TRUNCATE).
    """

    name: str
    socrata_id: str
    table: str
    columns: dict[str, str]
    key_columns: tuple[str, ...]
    date_column: str | None = "month"
    description: str = field(default="", compare=False)


DATASETS: dict[str, DatasetConfig] = {
    "terminal_otp": DatasetConfig(
        name="terminal_otp",
        socrata_id="f6rf-2a3t",
        table="terminal_otp",
        description="Terminal on-time performance by line/month (2015+)",
        columns={
            "month": "DATE",
            "division": "STRING",
            "line": "STRING",
            "day_type": "INT64",
            "num_on_time_trips": "FLOAT64",
            "num_sched_trips": "FLOAT64",
            "terminal_on_time_performance": "FLOAT64",
        },
        key_columns=("month", "line", "day_type"),
    ),
    "customer_journey": DatasetConfig(
        name="customer_journey",
        socrata_id="r7qk-6tcy",
        table="customer_journey",
        description="Customer journey-focused metrics by line/month (2015+)",
        columns={
            "month": "DATE",
            "division": "STRING",
            "line": "STRING",
            "period": "STRING",
            "num_passengers": "FLOAT64",
            "additional_platform_time": "FLOAT64",
            "additional_train_time": "FLOAT64",
            "total_apt": "FLOAT64",
            "total_att": "FLOAT64",
            "over_five_mins": "FLOAT64",
            "over_five_mins_perc": "FLOAT64",
            "customer_journey_time": "FLOAT64",
        },
        key_columns=("month", "line", "period"),
    ),
    "trains_delayed": DatasetConfig(
        name="trains_delayed",
        socrata_id="9zbp-wz3y",
        table="trains_delayed",
        description="Trains delayed by line/month/cause category (2020+)",
        columns={
            "month": "DATE",
            "division": "STRING",
            "line": "STRING",
            "day_type": "INT64",
            "reporting_category": "STRING",
            "delays": "FLOAT64",
        },
        key_columns=("month", "line", "day_type", "reporting_category"),
    ),
    "wait_assessment": DatasetConfig(
        name="wait_assessment",
        socrata_id="s666-h6b7",
        table="wait_assessment",
        description="Wait assessment (headway regularity) by line/month (2015+)",
        columns={
            "month": "DATE",
            "division": "STRING",
            "line": "STRING",
            "day_type": "INT64",
            "period": "STRING",
            "num_timepoints_passing_wait_assessment": "FLOAT64",
            "num_sched_timepoints": "FLOAT64",
            "wait_assessment": "FLOAT64",
        },
        key_columns=("month", "line", "day_type", "period"),
    ),
    "mdbf": DatasetConfig(
        name="mdbf",
        socrata_id="e2qc-xgxs",
        table="mdbf",
        description="Mean distance between failures by car class/month (2015+). "
        "Note: grain is car class, not line; mdbf arrives as text.",
        columns={
            "month": "DATE",
            "division": "STRING",
            "car_class": "STRING",
            "total_miles": "FLOAT64",
            "number_of_failures": "FLOAT64",
            "number_of_cars": "FLOAT64",
            "mdbf": "FLOAT64",
            "_12_month_average_mdbf": "FLOAT64",
        },
        key_columns=("month", "car_class"),
    ),
    "stations": DatasetConfig(
        name="stations",
        socrata_id="39hk-dx4f",
        table="stations",
        description="Subway station dimension: names, boroughs, routes, lat/long",
        columns={
            "gtfs_stop_id": "STRING",
            "station_id": "INT64",
            "complex_id": "INT64",
            "division": "STRING",
            "line": "STRING",
            "stop_name": "STRING",
            "borough": "STRING",
            "cbd": "STRING",
            "daytime_routes": "STRING",
            "structure": "STRING",
            "gtfs_latitude": "FLOAT64",
            "gtfs_longitude": "FLOAT64",
            "north_direction_label": "STRING",
            "south_direction_label": "STRING",
            "ada": "STRING",
        },
        key_columns=("gtfs_stop_id",),
        date_column=None,  # dimension table: full refresh every run
    ),
    "station_ridership": DatasetConfig(
        name="station_ridership",
        socrata_id="ak4z-sape",
        table="station_ridership",
        description="Monthly ridership by station complex (2017+)",
        columns={
            "month": "DATE",
            "station_complex_id": "STRING",
            "station_complex": "STRING",
            "borough": "STRING",
            "ridership": "FLOAT64",
            "transfers": "FLOAT64",
            "latitude": "FLOAT64",
            "longitude": "FLOAT64",
        },
        key_columns=("month", "station_complex_id"),
    ),
}
