"""Where has ridership come back, and where hasn't it?

Summarizes the ridership-recovery mart: system-wide recovery against the 2019
baseline, the split by borough, and the stations at each extreme. This is
descriptive rather than modeled, but it is the clearest narrative in the data.

Usage:
    python -m analysis.recovery
"""

from __future__ import annotations

import json
import logging

from analysis.data import OUTPUT_DIR, marts, query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("analysis.recovery")


def main() -> int:
    """Compute recovery summaries and write results."""
    df = query(f"SELECT * FROM {marts('mart_ridership_recovery')}")

    total_baseline = df["baseline_2019"].sum()
    total_recent = df["recent_ridership"].sum()
    system_recovery = round(total_recent / total_baseline * 100, 1)

    by_borough = (
        df.groupby("borough")
        .apply(lambda g: round(g["recent_ridership"].sum() / g["baseline_2019"].sum() * 100, 1),
               include_groups=False)
        .sort_values(ascending=False)
        .to_dict()
    )
    tier_counts = df["recovery_tier"].value_counts().to_dict()

    ranked = df.sort_values("recovery_pct", ascending=False)
    top = ranked.head(5)[["station_complex", "borough", "recovery_pct"]]
    bottom = ranked.tail(5)[["station_complex", "borough", "recovery_pct"]]

    logger.info("System ridership recovery vs 2019: %.1f%%", system_recovery)
    logger.info("By borough:")
    for boro, pct in by_borough.items():
        logger.info("  %-14s %.1f%%", boro, pct)
    logger.info("Recovery tiers: %s", tier_counts)
    logger.info("Strongest recovery:")
    for _, r in top.iterrows():
        logger.info("  %s (%s): %.1f%%", r["station_complex"], r["borough"], r["recovery_pct"])
    logger.info("Weakest recovery:")
    for _, r in bottom.iterrows():
        logger.info("  %s (%s): %.1f%%", r["station_complex"], r["borough"], r["recovery_pct"])

    out = OUTPUT_DIR / "recovery.json"
    out.write_text(json.dumps({
        "system_recovery_pct": system_recovery,
        "by_borough": by_borough,
        "tier_counts": {k: int(v) for k, v in tier_counts.items()},
        "strongest": [
            {"station": r["station_complex"], "borough": r["borough"],
             "recovery_pct": round(float(r["recovery_pct"]), 1)}
            for _, r in top.iterrows()
        ],
        "weakest": [
            {"station": r["station_complex"], "borough": r["borough"],
             "recovery_pct": round(float(r["recovery_pct"]), 1)}
            for _, r in bottom.iterrows()
        ],
    }, indent=2))
    logger.info("Wrote %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
