"""Page 6 — Insights: the modeling results (drivers, forecast, anomalies).

Reads the precomputed JSON in analysis/outputs so the dashboard stays fast and
does not refit models on load. Regenerate with `python -m analysis.run_all`.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import load_analysis_output

st.set_page_config(page_title="Insights — Transit Pulse", page_icon="🔬", layout="wide")


def render_drivers() -> None:
    """Driver regression: standardized coefficients and fit quality."""
    d = load_analysis_output("drivers")
    if not d:
        st.info("Run `python -m analysis.run_all` to generate driver results.")
        return
    st.subheader("What drives on-time performance")
    st.caption(
        f"Standardized linear regression over {d['n_observations']:,} line-months. "
        f"R² = {d['r_squared']} (cross-validated {d['cv_r_squared_mean']}), so the three "
        "operational factors explain about half the variance in on-time performance."
    )
    rows = [
        {"factor": d["labels"][f], "coef": d["features"][f]["std_coef"],
         "corr": d["features"][f]["corr_with_otp"]}
        for f in d["ranked_drivers"]
    ]
    df = pd.DataFrame(rows)
    fig = px.bar(
        df, x="coef", y="factor", orientation="h",
        color="coef", color_continuous_scale="RdBu", color_continuous_midpoint=0,
        labels={"coef": "Standardized coefficient (effect on OTP)", "factor": ""},
    )
    fig.update_layout(height=280, coloraxis_showscale=False)
    fig.add_vline(x=0, line_color="#888")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(
        "Wait assessment (even spacing) helps most; **ridership is the second-strongest "
        "factor and it is negative** — more riders independently predict worse "
        "performance, even after controlling for spacing and fleet reliability."
    )


def render_forecast() -> None:
    """Forecast backtest and an example forward projection."""
    f = load_analysis_output("forecast")
    if not f:
        return
    st.subheader("Forecasting on-time performance")
    c1, c2, c3 = st.columns(3)
    c1.metric("Holt-Winters MAE", f"{f['holt_winters']['mae']}", "points")
    c2.metric("Naive baseline MAE", f"{f['seasonal_naive']['mae']}", "points",
              delta_color="off")
    c3.metric("Model wins", f"{f['holt_winters_wins']}/{f['n_lines']}", "lines")
    st.caption(
        f"Backtested from {f['regime_start'][:7]} onward. {f['verdict'].capitalize()}. "
        "Monthly OTP is a short, break-heavy series, so a few points of error is the "
        "realistic ceiling."
    )
    ex = pd.DataFrame(f["example_forecast"])
    if not ex.empty:
        fig = go.Figure()
        fig.add_scatter(x=ex["month"], y=ex["forecast_otp_pct"], mode="lines+markers",
                        line={"color": "#2980b9"}, name="Forecast")
        fig.update_layout(height=300, yaxis_title="Forecast OTP (%)",
                          title=f"6-month forecast — {f['example_line']} line")
        st.plotly_chart(fig, use_container_width=True)


def render_anomalies() -> None:
    """Anomaly table matched to real events."""
    a = load_analysis_output("anomalies")
    if not a:
        return
    st.subheader("Anomaly detection")
    st.caption(
        f"{a['n_flagged']} of {a['n_line_months']:,} line-months flagged by robust "
        f"z-score (|z| ≥ {a['z_threshold']}) with a material-deviation gate. The worst "
        "line up with real events."
    )
    rows = a["top_anomalies"][:12]
    df = pd.DataFrame(rows)
    df["event"] = df["event"].fillna("—")
    df = df.rename(columns={"line": "Line", "month": "Month", "otp_pct": "OTP %",
                            "z": "z-score", "direction": "Direction", "event": "Known event"})
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    """Render the insights page."""
    st.title("🔬 Insights")
    st.markdown(
        "Modeling on top of the marts: what drives performance, whether it can be "
        "forecast, and which months were genuinely anomalous. Full write-up in "
        "`analysis/FINDINGS.md`."
    )
    render_drivers()
    st.divider()
    render_forecast()
    st.divider()
    render_anomalies()


if __name__ == "__main__":
    main()
