"""Page 3 — Time trends: OTP heatmap, rolling reliability, peak vs off-peak, YoY."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import (
    available_lines,
    filter_by_lines_and_dates,
    load_time_trends,
)

st.set_page_config(page_title="Time Trends — Transit Pulse", page_icon="📈", layout="wide")


def _filters(trends: pd.DataFrame) -> tuple[list[str], tuple]:
    """Resolve global filters from session state."""
    lines = st.session_state.get("selected_lines") or available_lines()
    periods = pd.to_datetime(trends["period"])
    default_range = (periods.min().date(), periods.max().date())
    return lines, st.session_state.get("date_range", default_range)


def main() -> None:
    """Render the time-trends page."""
    st.title("📈 Time Trends")
    trends = load_time_trends()
    lines, date_range = _filters(trends)
    data = filter_by_lines_and_dates(trends, lines, date_range).copy()

    if data.empty:
        st.warning("No data for the current filters. Adjust the sidebar.")
        return

    data["period"] = pd.to_datetime(data["period"])
    data["month_label"] = data["period"].dt.strftime("%Y-%m")

    st.subheader("On-time performance heatmap (line × month)")
    pivot = data.pivot_table(index="line_name", columns="month_label",
                             values="overall_otp_pct", aggfunc="mean")
    fig_heat = px.imshow(
        pivot,
        color_continuous_scale="RdYlGn",
        aspect="auto",
        labels={"x": "Month", "y": "Line", "color": "OTP %"},
        zmin=50, zmax=100,
    )
    fig_heat.update_layout(height=max(400, 26 * len(pivot)))
    st.plotly_chart(fig_heat, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Rolling 3-month OTP")
        fig_roll = px.line(
            data.sort_values("period"),
            x="period", y="rolling_3mo_otp_pct", color="line_name",
            labels={"rolling_3mo_otp_pct": "Rolling 3-mo OTP (%)",
                    "period": "Month", "line_name": "Line"},
        )
        fig_roll.update_layout(height=420, hovermode="x unified", legend_title_text="Line")
        st.plotly_chart(fig_roll, use_container_width=True)

    with col2:
        st.subheader("Peak vs off-peak journey time")
        peak = data.groupby("line_name", as_index=False)[["peak_cjt_pct", "offpeak_cjt_pct"]].mean()
        fig_peak = go.Figure()
        fig_peak.add_bar(x=peak["line_name"], y=peak["peak_cjt_pct"], name="Peak",
                         marker_color="#e67e22")
        fig_peak.add_bar(x=peak["line_name"], y=peak["offpeak_cjt_pct"], name="Off-peak",
                         marker_color="#3498db")
        fig_peak.update_layout(height=420, barmode="group", yaxis_title="Journey time score (%)",
                               xaxis_title="Line")
        st.plotly_chart(fig_peak, use_container_width=True)

    st.subheader("Year-over-year — same-month comparison")
    latest_period = data["period"].max()
    same_month = data[data["period"].dt.month == latest_period.month]
    yoy = same_month.groupby(same_month["period"].dt.year, as_index=False)["overall_otp_pct"].mean()
    yoy.columns = ["year", "avg_otp_pct"]
    fig_yoy = px.bar(yoy, x="year", y="avg_otp_pct", text="avg_otp_pct",
                     labels={"avg_otp_pct": "Avg OTP (%)", "year": "Year"})
    fig_yoy.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_yoy.update_layout(height=380)
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
