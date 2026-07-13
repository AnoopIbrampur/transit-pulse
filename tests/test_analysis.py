"""Unit tests for analysis helpers that don't require BigQuery.

The network-dependent parts (loading marts) are not tested here; these cover the
pure statistical functions so CI can validate the logic offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.anomalies import robust_z
from analysis.forecast import _metrics


def test_robust_z_flags_outlier() -> None:
    """A clear low outlier should get a strongly negative robust z-score."""
    series = pd.Series([90.0, 91.0, 89.0, 90.5, 40.0, 90.2, 89.8])
    z = robust_z(series)
    assert z.iloc[4] < -3.5  # the 40.0 value
    assert z.drop(index=4).abs().max() < 3.5  # nothing else flagged


def test_robust_z_zero_spread() -> None:
    """A constant series has no spread and yields all-zero scores."""
    z = robust_z(pd.Series([88.0, 88.0, 88.0, 88.0]))
    assert (z == 0).all()


def test_metrics_perfect_prediction() -> None:
    """Exact predictions produce zero error."""
    actual = np.array([80.0, 82.0, 78.0])
    mae, rmse = _metrics(actual, actual.copy())
    assert mae == 0.0
    assert rmse == 0.0


def test_metrics_known_values() -> None:
    """MAE and RMSE match hand-computed values."""
    actual = np.array([10.0, 20.0, 30.0])
    pred = np.array([12.0, 18.0, 33.0])  # errors: -2, +2, -3
    mae, rmse = _metrics(actual, pred)
    assert abs(mae - (7 / 3)) < 1e-9
    assert abs(rmse - np.sqrt((4 + 4 + 9) / 3)) < 1e-9
