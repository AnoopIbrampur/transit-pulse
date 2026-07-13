"""Run every analysis module in sequence and refresh the outputs/ JSON files.

Usage:
    python -m analysis.run_all
"""

from __future__ import annotations

import logging

from analysis import anomalies, drivers, forecast, recovery

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("analysis.run_all")


def main() -> int:
    """Run all analyses; return non-zero if any fails."""
    steps = [
        ("driver regression", drivers.main),
        ("OTP forecast backtest", forecast.main),
        ("anomaly detection", anomalies.main),
        ("ridership recovery", recovery.main),
    ]
    failures = 0
    for name, fn in steps:
        logger.info("=== %s ===", name)
        try:
            if fn() != 0:
                failures += 1
        except Exception:
            logger.exception("%s failed", name)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
