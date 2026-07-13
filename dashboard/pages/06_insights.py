"""Page 6 — Insights: the modeling results (drivers, forecast, anomalies).

Reads the precomputed JSON in analysis/outputs so the dashboard stays fast and
does not refit models on load. Regenerate with `python -m analysis.run_all`.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import theme
from data import load_analysis_output

theme.setup("Insights")


def render_drivers() -> None:
    """Driver regression: standardized coefficients and fit quality."""
    d = load_analysis_output("drivers")
    if not d:
        st.info("Run `python -m analysis.run_all` to generate driver results.")
        return
    st.subheader("What drives on-time performance")
    st.caption(
        f"Standardized linear regression over {d['n_observations']:,} line-months. "
        f"R² = {d['r_squared']} (cross-validated {d['cv_r_squared_mean']}) — the three "
        "operational factors explain about half the variance in on-time performance."
    )
    rows = [
        {"factor": d["labels"][f], "coef": d["features"][f]["std_coef"]}
        for f in d["ranked_drivers"]
    ][::-1]  # weakest at top so the strongest driver sits at the bottom axis
    df = pd.DataFrame(rows)
    colors = [theme.DIVERGE_POS if c >= 0 else theme.DIVERGE_NEG for c in df["coef"]]
    fig = go.Figure(go.Bar(
        x=df["coef"], y=df["factor"], orientation="h",
        marker_color=colors, marker_line_width=0,
        text=[f"{c:+.1f}" for c in df["coef"]], textposition="outside",
    ))
    fig.update_layout(
        height=280, bargap=0.4,
        xaxis_title="Standardized coefficient (effect on OTP)",
        xaxis_range=[-8, 8],
    )
    fig.add_vline(x=0, line_color="#B9B9B2")
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
        line = f["example_line"]
        fig = go.Figure()
        fig.add_scatter(
            x=ex["month"], y=ex["forecast_otp_pct"], mode="lines+markers+text",
            line=dict(color=theme.route_color(line), width=2.4),
            marker=dict(size=8),
            text=[f"{v:.0f}" for v in ex["forecast_otp_pct"]],
            textposition="top center", textfont=dict(size=11, color=theme.INK_SOFT),
            name="Forecast",
        )
        fig.update_layout(height=320, yaxis_title="Forecast OTP (%)",
                          title=f"Six-month forecast — {line} line", showlegend=False)
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
    theme.sign(
        "Insights",
        sub="Modeling on top of the marts — full write-up in analysis/FINDINGS.md",
    )
    render_drivers()
    st.divider()
    render_forecast()
    st.divider()
    render_anomalies()


if __name__ == "__main__":
    main()
