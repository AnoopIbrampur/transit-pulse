"""Forecast on-time performance per line, and check whether it is worth it.

Monthly OTP per line is a short series (roughly a decade) with a large structural
break in 2020, so this is a hard forecasting problem and worth being honest about.
The module backtests a Holt-Winters exponential-smoothing model against a
seasonal-naive baseline (this month last year) using a rolling origin over the
most recent months, and reports error metrics for both. If the model cannot beat
the naive baseline, that is the finding.

To keep the regime consistent, only the post-recovery period (2021-07 onward) is
used, so the pandemic collapse does not dominate the fit.

Usage:
    python -m analysis.forecast
"""

from __future__ import annotations

import json
import logging
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from analysis.data import OUTPUT_DIR, marts, query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("analysis.forecast")

REGIME_START = "2021-07-01"
BACKTEST_MONTHS = 9   # rolling-origin horizon-1 evaluations
HORIZON = 6           # months to forecast forward for the published example


def load_series() -> pd.DataFrame:
    """Load monthly weekday OTP per line for the post-recovery regime.

    Returns:
        DataFrame indexed by (line_name, period) with an otp_pct column.
    """
    frame = query(
        f"SELECT line_name, period, otp_pct FROM {marts('mart_line_reliability')} "
        f"WHERE period >= '{REGIME_START}' ORDER BY line_name, period"
    )
    frame["period"] = pd.to_datetime(frame["period"])
    return frame


def _metrics(actual: np.ndarray, pred: np.ndarray) -> tuple[float, float]:
    """Return (MAE, RMSE) for aligned actual/predicted arrays."""
    err = actual - pred
    return float(np.mean(np.abs(err))), float(np.sqrt(np.mean(err**2)))


def backtest_line(series: pd.Series) -> dict | None:
    """Rolling-origin backtest of Holt-Winters vs seasonal-naive for one line.

    Args:
        series: Monthly OTP for a single line, chronologically ordered.

    Returns:
        Per-line MAE/RMSE for both methods, or None if the series is too short.
    """
    values = series.to_numpy(dtype=float)
    if len(values) < 12 + BACKTEST_MONTHS + 12:  # need seasonal history + naive lag
        return None

    hw_pred, naive_pred, actual = [], [], []
    for step in range(BACKTEST_MONTHS, 0, -1):
        train = values[:-step]
        truth = values[-step]
        actual.append(truth)
        naive_pred.append(train[-12])  # same month last year
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                model = ExponentialSmoothing(
                    train, trend="add", seasonal="add", seasonal_periods=12,
                    initialization_method="estimated",
                ).fit()
                hw_pred.append(float(model.forecast(1)[0]))
            except Exception:
                hw_pred.append(train[-12])  # fall back to naive on fit failure

    hw_mae, hw_rmse = _metrics(np.array(actual), np.array(hw_pred))
    nv_mae, nv_rmse = _metrics(np.array(actual), np.array(naive_pred))
    return {"hw_mae": hw_mae, "hw_rmse": hw_rmse, "naive_mae": nv_mae, "naive_rmse": nv_rmse}


def forward_forecast(series: pd.Series, horizon: int) -> list[dict]:
    """Fit Holt-Winters on the full series and forecast forward.

    Args:
        series: Monthly OTP for a single line.
        horizon: Number of months to project.

    Returns:
        List of {month, forecast_otp_pct} dicts.
    """
    values = series.to_numpy(dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(
            values, trend="add", seasonal="add", seasonal_periods=12,
            initialization_method="estimated",
        ).fit()
    preds = model.forecast(horizon)
    last = series.index[-1]
    months = pd.date_range(last, periods=horizon + 1, freq="MS")[1:]
    return [
        {"month": m.strftime("%Y-%m"), "forecast_otp_pct": round(float(p), 1)}
        for m, p in zip(months, preds)
    ]


def main() -> int:
    """Backtest every line, summarize, and publish an example forecast."""
    frame = load_series()
    per_line = {}
    for line, grp in frame.groupby("line_name"):
        series = grp.set_index("period")["otp_pct"]
        result = backtest_line(series)
        if result is not None:
            per_line[line] = result

    if not per_line:
        logger.error("No lines had enough history to backtest")
        return 1

    hw_mae = np.mean([r["hw_mae"] for r in per_line.values()])
    nv_mae = np.mean([r["naive_mae"] for r in per_line.values()])
    hw_rmse = np.mean([r["hw_rmse"] for r in per_line.values()])
    nv_rmse = np.mean([r["naive_rmse"] for r in per_line.values()])
    wins = sum(1 for r in per_line.values() if r["hw_mae"] < r["naive_mae"])

    verdict = (
        "Holt-Winters beats the naive baseline"
        if hw_mae < nv_mae
        else "the seasonal-naive baseline is competitive — extra model complexity is not justified"
    )
    logger.info("Backtested %d lines over %d months each", len(per_line), BACKTEST_MONTHS)
    logger.info("Holt-Winters  MAE=%.2f  RMSE=%.2f", hw_mae, hw_rmse)
    logger.info("Seasonal-naive MAE=%.2f  RMSE=%.2f", nv_mae, nv_rmse)
    logger.info("Holt-Winters wins on %d/%d lines. Verdict: %s", wins, len(per_line), verdict)

    # Example forward forecast for the busiest workhorse line present.
    example_line = "7" if "7" in per_line else next(iter(per_line))
    series = frame[frame["line_name"] == example_line].set_index("period")["otp_pct"]
    example = forward_forecast(series, HORIZON)
    logger.info("Example %d-month forecast for the %s line: %s",
                HORIZON, example_line, [e["forecast_otp_pct"] for e in example])

    out = OUTPUT_DIR / "forecast.json"
    out.write_text(json.dumps({
        "regime_start": REGIME_START,
        "backtest_months": BACKTEST_MONTHS,
        "n_lines": len(per_line),
        "holt_winters": {"mae": round(hw_mae, 2), "rmse": round(hw_rmse, 2)},
        "seasonal_naive": {"mae": round(nv_mae, 2), "rmse": round(nv_rmse, 2)},
        "holt_winters_wins": wins,
        "verdict": verdict,
        "example_line": example_line,
        "example_forecast": example,
    }, indent=2))
    logger.info("Wrote %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
