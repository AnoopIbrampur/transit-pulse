"""What drives on-time performance?

Fits a standardized multiple linear regression of weekday on-time performance
on the operational factors available at line-month grain: ridership, headway
regularity (wait assessment), and fleet reliability (mean distance between
failures). Standardizing the features puts the coefficients on the same scale,
so their magnitudes are directly comparable as driver strengths.

The headline result is the ridership coefficient: more riders, worse on-time
performance, holding the other factors constant.

Usage:
    python -m analysis.drivers
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.model_selection import KFold, cross_val_score
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from analysis.data import OUTPUT_DIR, marts, query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("analysis.drivers")

FEATURES = {
    "total_passengers": "Ridership (monthly passengers)",
    "wait_assessment_pct": "Wait assessment (headway regularity)",
    "avg_fleet_mdbf": "Fleet reliability (MDBF)",
}
TARGET = "otp_pct"


def load_panel() -> pd.DataFrame:
    """Load the line-month panel and drop rows missing any model column.

    Returns:
        DataFrame with the target and feature columns, fully populated.
    """
    cols = [TARGET, *FEATURES]
    frame = query(
        f"SELECT line_name, period, {', '.join(cols)} "
        f"FROM {marts('mart_line_reliability')}"
    )
    before = len(frame)
    frame = frame.dropna(subset=cols).reset_index(drop=True)
    logger.info("Panel: %d line-months (%d dropped for missing values)", len(frame), before - len(frame))
    return frame


def fit(frame: pd.DataFrame) -> dict:
    """Fit the standardized regression and cross-validate it.

    Args:
        frame: The line-month panel.

    Returns:
        A results dict with standardized coefficients, R^2, cross-validated R^2,
        and pairwise correlations of each feature with the target.
    """
    x_raw = frame[list(FEATURES)].to_numpy(dtype=float)
    y = frame[TARGET].to_numpy(dtype=float)
    x = StandardScaler().fit_transform(x_raw)

    # statsmodels for inference (coefficients, p-values, R^2).
    ols = sm.OLS(y, sm.add_constant(x)).fit()
    coefs = {
        name: {
            "std_coef": round(float(ols.params[i + 1]), 3),
            "p_value": round(float(ols.pvalues[i + 1]), 4),
            "corr_with_otp": round(float(np.corrcoef(x_raw[:, i], y)[0, 1]), 3),
        }
        for i, name in enumerate(FEATURES)
    }

    # sklearn for an honest out-of-sample R^2 via 5-fold CV.
    cv = cross_val_score(
        LinearRegression(), x, y, cv=KFold(5, shuffle=True, random_state=42), scoring="r2"
    )

    results = {
        "n_observations": int(len(frame)),
        "r_squared": round(float(ols.rsquared), 3),
        "cv_r_squared_mean": round(float(cv.mean()), 3),
        "cv_r_squared_std": round(float(cv.std()), 3),
        "features": coefs,
        "ranked_drivers": sorted(
            FEATURES, key=lambda f: abs(coefs[f]["std_coef"]), reverse=True
        ),
    }
    return results


def main() -> int:
    """Run the driver analysis and write results to analysis/outputs."""
    frame = load_panel()
    results = fit(frame)

    logger.info("R^2 = %.3f (CV R^2 = %.3f ± %.3f)",
                results["r_squared"], results["cv_r_squared_mean"], results["cv_r_squared_std"])
    logger.info("Drivers of on-time performance, strongest first:")
    for name in results["ranked_drivers"]:
        c = results["features"][name]
        direction = "lowers" if c["std_coef"] < 0 else "raises"
        logger.info("  %-40s std β=%+.3f  (%s OTP, p=%.4f, r=%+.3f)",
                    FEATURES[name], c["std_coef"], direction, c["p_value"], c["corr_with_otp"])

    out = OUTPUT_DIR / "drivers.json"
    out.write_text(json.dumps({"labels": FEATURES, **results}, indent=2))
    logger.info("Wrote %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
