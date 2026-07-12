"""Unit tests for the ingestion dataset registry and schema conformance.

These run in CI with no network access and no BigQuery credentials.
"""

from __future__ import annotations

import pandas as pd

from ingestion.config import DATASETS
from ingestion.mta_ingest import conform_schema


def test_registry_keys_match_names() -> None:
    """Registry dict keys must equal each config's name."""
    for key, config in DATASETS.items():
        assert key == config.name


def test_key_columns_exist_in_schema() -> None:
    """Every natural-key column must be part of the declared schema."""
    for config in DATASETS.values():
        for key_col in config.key_columns:
            assert key_col in config.columns, f"{config.name}: {key_col} missing"


def test_date_column_exists_in_schema() -> None:
    """Incremental date columns must be part of the declared schema."""
    for config in DATASETS.values():
        if config.date_column is not None:
            assert config.date_column in config.columns


def test_conform_schema_casts_and_dedupes() -> None:
    """conform_schema casts Socrata strings and drops natural-key duplicates."""
    config = DATASETS["terminal_otp"]
    frame = pd.DataFrame(
        [
            {
                "month": "2025-01-01T00:00:00.000",
                "division": "A DIVISION",
                "line": "1",
                "day_type": "1",
                "num_on_time_trips": "6874",
                "num_sched_trips": "9017",
                "terminal_on_time_performance": "0.762",
                "unexpected_extra_column": "dropme",
            },
            {  # exact duplicate on the (month, line, day_type) key
                "month": "2025-01-01T00:00:00.000",
                "division": "A DIVISION",
                "line": "1",
                "day_type": "1",
                "num_on_time_trips": "9999",
                "num_sched_trips": "9999",
                "terminal_on_time_performance": "0.999",
            },
        ]
    )
    out = conform_schema(config, frame)
    assert len(out) == 1
    assert "unexpected_extra_column" not in out.columns
    assert list(out.columns) == list(config.columns)
    assert out.loc[0, "day_type"] == 1
    assert abs(out.loc[0, "terminal_on_time_performance"] - 0.762) < 1e-9
    assert str(out.loc[0, "month"]) == "2025-01-01"


def test_conform_schema_handles_empty_frame() -> None:
    """An empty API response must produce an empty, well-typed frame."""
    config = DATASETS["stations"]
    out = conform_schema(config, pd.DataFrame())
    assert out.empty
    assert list(out.columns) == list(config.columns)
