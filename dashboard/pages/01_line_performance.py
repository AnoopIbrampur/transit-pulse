"""Page 1 — Line performance overview: KPI cards, OTP ranking, OTP trends."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import theme
from data import (
    available_lines,
    filter_by_lines_and_dates,
    load_line_reliability,
)

theme.setup("Line Performance")


def _filters(reliability: pd.DataFrame) -> tuple[list[str], tuple]:
    """Resolve global filters from session state, falling back to all lines."""
    lines = st.session_state.get("selected_lines") or available_lines()
    periods = pd.to_datetime(reliability["period"])
    default_range = (periods.min().date(), periods.max().date())
    date_range = st.session_state.get("date_range", default_range)
    return lines, date_range


def main() -> None:
    """Render the line-performance page."""
    reliability = load_line_reliability()
    lines, date_range = _filters(reliability)
    data = filter_by_lines_and_dates(reliability, lines, date_range)

    if data.empty:
        theme.sign("Line performance")
        st.warning("No data for the current filters. Adjust the sidebar.")
        return

    latest_period = data["period"].max()
    latest = data[data["period"] == latest_period].copy()
    theme.sign(
        "Line performance",
        sub=f"Snapshot {pd.to_datetime(latest_period):%B %Y} · "
            f"{latest['line_name'].nunique()} lines in view",
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Lines in view", f"{latest['line_name'].nunique()}")
    c2.metric("Best OTP", f"{latest['otp_pct'].max():.1f}%",
              latest.loc[latest['otp_pct'].idxmax(), 'line_name'])
    c3.metric("Avg health score", f"{latest['line_health_score'].mean():.1f}")
    st.write("")

    st.subheader("On-time performance by line")
    st.caption("Latest month, ranked. Colored by reliability tier — "
               "reliable ≥ 90%, at risk 80–90%, poor < 80%.")
    ranked = latest.sort_values("otp_pct")
    fig_bar = px.bar(
        ranked,
        x="otp_pct",
        y="line_name",
        orientation="h",
        color="reliability_tier",
        color_discrete_map=theme.TIER_COLORS,
        labels={"otp_pct": "On-time performance (%)", "line_name": "Line",
                "reliability_tier": "Tier"},
        text="otp_pct",
    )
    fig_bar.update_traces(texttemplate="%{text:.0f}%", textposition="outside",
                          marker_line_width=0)
    fig_bar.update_layout(height=max(420, 24 * len(ranked)), yaxis_title=None,
                          legend_title_text="Reliability tier", bargap=0.35)
    fig_bar.add_vline(x=90, line_dash="dot", line_color=theme.GOOD,
                      annotation_text="90%")
    fig_bar.add_vline(x=80, line_dash="dot", line_color=theme.BAD,
                      annotation_text="80%")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("On-time performance over time")
    st.caption("Lines wear their official route colors — red is the 1/2/3 trunk, "
               "orange the B/D/F/M, and so on. Hover for exact values.")
    fig_line = px.line(
        data.sort_values("period"),
        x="period",
        y="otp_pct",
        color="line_name",
        color_discrete_map=theme.ROUTE_COLORS,
        labels={"otp_pct": "On-time performance (%)", "period": "Month", "line_name": "Line"},
    )
    fig_line.update_traces(line_width=2.2)
    fig_line.update_layout(height=480, legend_title_text="Line", hovermode="x unified")
    fig_line.add_hline(y=90, line_dash="dot", line_color=theme.GOOD)
    st.plotly_chart(fig_line, use_container_width=True)

    with st.expander("View underlying data"):
        st.dataframe(
            latest[["line_name", "otp_pct", "wait_assessment_pct", "cjt_pct",
                    "line_health_score", "reliability_tier", "total_passengers"]]
            .sort_values("line_health_score", ascending=False),
            use_container_width=True, hide_index=True,
        )


if __name__ == "__main__":
    main()
