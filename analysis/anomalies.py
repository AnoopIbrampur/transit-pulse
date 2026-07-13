"""Flag anomalous line-months and tie the biggest ones to real events.

Uses a robust per-line z-score (median and median-absolute-deviation, which are
not dragged around by the very outliers we are hunting) to score how unusual each
month's on-time performance is for that line. Months past a threshold are flagged;
the most extreme are matched against a short list of known NYC transit events so
the statistics line up with what actually happened.

Usage:
    python -m analysis.anomalies
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from analysis.data import OUTPUT_DIR, marts, query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("analysis.anomalies")

Z_THRESHOLD = 3.5    # modified z-score cutoff for flagging
MIN_ABS_DEV = 8.0    # also require an 8-point deviation from the line's own median,
                     # so ultra-stable shuttles don't flag on a trivial 4-point dip

# Known events, matched to flagged months within a two-month window.
KNOWN_EVENTS = {
    "2017-06": "Summer of Hell: track fire and derailments at Penn/Harlem",
    "2017-07": "Summer of Hell: emergency repair program",
    "2020-04": "COVID shutdown: near-empty trains ran close to schedule",
    "2020-05": "COVID shutdown: ridership at historic lows",
    "2021-09": "Hurricane Ida flooding across the network",
}


def load() -> pd.DataFrame:
    """Load line-month OTP for anomaly scoring."""
    frame = query(
        f"SELECT line_name, period, otp_pct FROM {marts('mart_line_reliability')} "
        f"ORDER BY line_name, period"
    )
    frame["period"] = pd.to_datetime(frame["period"])
    frame["month"] = frame["period"].dt.strftime("%Y-%m")
    return frame


def robust_z(series: pd.Series) -> pd.Series:
    """Return the modified (median/MAD) z-score of a series.

    Args:
        series: Numeric values for one line.

    Returns:
        Signed robust z-scores; 0 where the series has no spread.
    """
    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return 0.6745 * (series - median) / mad


def main() -> int:
    """Score anomalies, match known events, and write results."""
    frame = load()
    frame["z"] = frame.groupby("line_name")["otp_pct"].transform(robust_z)
    frame["median_otp"] = frame.groupby("line_name")["otp_pct"].transform("median")
    frame["abs_dev"] = (frame["otp_pct"] - frame["median_otp"]).abs()
    frame["direction"] = np.where(frame["z"] < 0, "worse than usual", "better than usual")

    flagged = frame[
        (frame["z"].abs() >= Z_THRESHOLD) & (frame["abs_dev"] >= MIN_ABS_DEV)
    ].copy()
    flagged["event"] = flagged["month"].map(KNOWN_EVENTS)
    flagged = flagged.sort_values("z")  # most negative (worst) first

    logger.info("Flagged %d anomalous line-months (|z| >= %.1f) out of %d",
                len(flagged), Z_THRESHOLD, len(frame))

    worst = flagged.head(10)
    logger.info("Ten most anomalous (worst) line-months:")
    for _, r in worst.iterrows():
        tag = f"  [{r['event']}]" if isinstance(r["event"], str) else ""
        logger.info("  %s line, %s: OTP %.1f%% (z=%.1f, %s)%s",
                    r["line_name"], r["month"], r["otp_pct"], r["z"], r["direction"], tag)

    matched = int(flagged["event"].notna().sum())
    logger.info("%d flagged months matched a known event", matched)

    out = OUTPUT_DIR / "anomalies.json"
    out.write_text(json.dumps({
        "z_threshold": Z_THRESHOLD,
        "n_flagged": int(len(flagged)),
        "n_line_months": int(len(frame)),
        "n_matched_to_events": matched,
        "top_anomalies": [
            {
                "line": r["line_name"], "month": r["month"],
                "otp_pct": round(float(r["otp_pct"]), 1), "z": round(float(r["z"]), 2),
                "direction": r["direction"],
                "event": r["event"] if isinstance(r["event"], str) else None,
            }
            for _, r in flagged.head(25).iterrows()
        ],
    }, indent=2))
    logger.info("Wrote %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
