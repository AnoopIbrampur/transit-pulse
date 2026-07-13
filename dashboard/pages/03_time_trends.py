"""Page 3 — Time trends: OTP heatmap, rolling reliability, peak vs off-peak, YoY."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import theme
from data import (
    available_lines,
    filter_by_lines_and_dates,
    load_time_trends,
)

theme.setup("Time Trends")

# Diverging scale around the network's long-run OTP (~82%): red below, blue above.
HEAT_SCALE = [(0.0, theme.DIVERGE_NEG), (0.5, theme.DIVERGE_MID), (1.0, theme.DIVERGE_POS)]
HEAT_MIN, HEAT_MAX = 64, 100  # midpoint lands at 82


def _filters(trends: pd.DataFrame) -> tuple[list[str], tuple]:
    """Resolve global filters from session state."""
    lines = st.session_state.get("selected_lines") or available_lines()
    periods = pd.to_datetime(trends["period"])
    default_range = (periods.min().date(), periods.max().date())
    return lines, st.session_state.get("date_range", default_range)


def main() -> None:
    """Render the time-trends page."""
    trends = load_time_trends()
    lines, date_range = _filters(trends)
    data = filter_by_lines_and_dates(trends, lines, date_range).copy()

    if data.empty:
        theme.sign("Time trends")
        st.warning("No data for the current filters. Adjust the sidebar.")
        return

    data["period"] = pd.to_datetime(data["period"])
    data["month_label"] = data["period"].dt.strftime("%Y-%m")
    theme.sign(
        "Time trends",
        sub=f"{data['month_label'].nunique()} months · seasonality, rolling reliability, "
            "and year-over-year comparisons",
    )

    st.subheader("On-time performance heatmap")
    st.caption("Line by month. Red sits below the network's long-run 82% average, "
               "blue above it — the 2017–18 crisis and the 2020 empty-train spike "
               "both stand out.")
    pivot = data.pivot_table(index="line_name", columns="month_label",
                             values="overall_otp_pct", aggfunc="mean")
    fig_heat = px.imshow(
        pivot,
        color_continuous_scale=HEAT_SCALE,
        aspect="auto",
        labels={"x": "Month", "y": "Line", "color": "OTP %"},
        zmin=HEAT_MIN, zmax=HEAT_MAX,
    )
    fig_heat.update_layout(height=max(420, 26 * len(pivot)),
                           coloraxis_colorbar=dict(title="OTP %"))
    st.plotly_chart(fig_heat, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Rolling 3-month OTP")
        fig_roll = px.line(
            data.sort_values("period"),
            x="period", y="rolling_3mo_otp_pct", color="line_name",
            color_discrete_map=theme.ROUTE_COLORS,
            labels={"rolling_3mo_otp_pct": "Rolling 3-mo OTP (%)",
                    "period": "Month", "line_name": "Line"},
        )
        fig_roll.update_traces(line_width=2)
        fig_roll.update_layout(height=420, hovermode="x unified", legend_title_text="Line")
        st.plotly_chart(fig_roll, use_container_width=True)

    with col2:
        st.subheader("Peak vs off-peak journey time")
        peak = data.groupby("line_name", as_index=False)[["peak_cjt_pct", "offpeak_cjt_pct"]].mean()
        fig_peak = go.Figure()
        fig_peak.add_bar(x=peak["line_name"], y=peak["peak_cjt_pct"], name="Peak",
                         marker_color=theme.CATEGORICAL[0])
        fig_peak.add_bar(x=peak["line_name"], y=peak["offpeak_cjt_pct"], name="Off-peak",
                         marker_color=theme.CATEGORICAL[2])
        fig_peak.update_layout(height=420, barmode="group", bargap=0.3,
                               yaxis_title="Journey time score (%)", xaxis_title="Line")
        st.plotly_chart(fig_peak, use_container_width=True)

    st.subheader("Year-over-year, same month")
    latest_period = data["period"].max()
    same_month = data[data["period"].dt.month == latest_period.month]
    yoy = same_month.groupby(same_month["period"].dt.year, as_index=False)["overall_otp_pct"].mean()
    yoy.columns = ["year", "avg_otp_pct"]
    fig_yoy = px.bar(yoy, x="year", y="avg_otp_pct", text="avg_otp_pct",
                     labels={"avg_otp_pct": "Avg OTP (%)", "year": "Year"})
    fig_yoy.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                          marker_color=theme.CATEGORICAL[0], marker_line_width=0)
    fig_yoy.update_layout(height=380, bargap=0.45)
    st.plotly_chart(fig_yoy, use_container_width=True)
    st.caption(f"Comparing {latest_period:%B} across years.")

    monthly_avg = data.groupby("month_label", as_index=False)["overall_otp_pct"].mean()
    best = monthly_avg.loc[monthly_avg["overall_otp_pct"].idxmax()]
    worst = monthly_avg.loc[monthly_avg["overall_otp_pct"].idxmin()]
    b, w = st.columns(2)
    b.metric("Best month (avg OTP)", best["month_label"], f"{best['overall_otp_pct']:.1f}%")
    w.metric("Worst month (avg OTP)", worst["month_label"], f"{worst['overall_otp_pct']:.1f}%",
             delta_color="inverse")


if __name__ == "__main__":
    main()
