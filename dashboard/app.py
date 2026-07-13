"""Transit Pulse — NYC MTA subway analytics dashboard (Streamlit entry point).

Landing page: a station-sign hero, headline KPIs, and the global sidebar
filters (line multiselect + date range) that every page reads from
``st.session_state``.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import theme
from data import (
    available_lines,
    filter_by_lines_and_dates,
    load_line_reliability,
)

theme.setup("NYC MTA Analytics")

# Canonical bullet order for the hero strip (trunk-line groupings).
HERO_ROUTES = ["1", "2", "3", "4", "5", "6", "7",
               "A", "C", "E", "B", "D", "F", "M",
               "G", "J", "Z", "L", "N", "Q", "R", "W", "S"]


def render_sidebar(reliability: pd.DataFrame) -> tuple[list[str], tuple]:
    """Render the global sidebar filters and persist them in session state.

    Args:
        reliability: The line-reliability mart (drives filter bounds).

    Returns:
        (selected_lines, (start_date, end_date)) — also stored in session_state.
    """
    st.sidebar.title("Transit Pulse")
    st.sidebar.caption("NYC MTA subway performance analytics")

    lines = available_lines()
    selected = st.sidebar.multiselect(
        "Subway lines",
        options=lines,
        default=lines,
        help="Filter every page to these lines.",
    )

    periods = pd.to_datetime(reliability["period"])
    min_date, max_date = periods.min().date(), periods.max().date()
    date_range = st.sidebar.slider(
        "Date range",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="YYYY-MM",
    )

    st.sidebar.divider()
    st.sidebar.subheader("About the data")
    st.sidebar.markdown(
        "Source: [NY Open Data](https://data.ny.gov) — MTA subway performance "
        "datasets (2015–present), refreshed monthly. Metrics: terminal on-time "
        "performance, wait assessment, customer journey time, delays, mean "
        "distance between failures, and station ridership."
    )
    st.sidebar.caption("Pipeline: SODA API → BigQuery → dbt → Streamlit")

    st.session_state["selected_lines"] = selected
    st.session_state["date_range"] = date_range
    return selected, date_range


def render_kpis(reliability: pd.DataFrame, lines: list[str], date_range: tuple) -> None:
    """Render the headline KPI cards for the current filter selection.

    Args:
        reliability: The line-reliability mart.
        lines: Selected line names.
        date_range: (start, end) date tuple.
    """
    filtered = filter_by_lines_and_dates(reliability, lines, date_range)
    if filtered.empty:
        st.warning("No data for the current filters.")
        return

    latest_period = filtered["period"].max()
    latest = filtered[filtered["period"] == latest_period]

    avg_otp = latest["otp_pct"].mean()
    avg_health = latest["line_health_score"].mean()
    total_riders = latest["total_passengers"].sum()
    worst_row = latest.loc[latest["otp_pct"].idxmin()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg on-time", f"{avg_otp:.1f}%")
    c2.metric("Line health score", f"{avg_health:.1f}")
    c3.metric("Monthly passengers", f"{total_riders/1e6:.1f}M")
    c4.metric(
        "Worst line (OTP)",
        f"{worst_row['line_name']}",
        f"{worst_row['otp_pct']:.1f}%",
        delta_color="inverse",
    )
    st.caption(f"KPIs reflect the latest month in range: {pd.to_datetime(latest_period):%B %Y}")


def render_explore() -> None:
    """Render the page directory as link cards."""
    st.subheader("Explore")
    rows = [
        [
            ("pages/01_line_performance.py", "Line performance",
             "On-time rankings and trends by line."),
            ("pages/02_station_delays.py", "Station delay map",
             "Geospatial reliability across 496 stations."),
            ("pages/03_time_trends.py", "Time trends",
             "Seasonality, peak vs off-peak, year over year."),
        ],
        [
            ("pages/04_delay_causes.py", "Delay causes",
             "What makes trains late, and how the mix shifted."),
            ("pages/05_ridership_recovery.py", "Ridership recovery",
             "Post-pandemic recovery by station and borough."),
            ("pages/06_insights.py", "Insights",
             "Driver regression, forecasting, anomaly detection."),
        ],
    ]
    for row in rows:
        cols = st.columns(3)
        for col, (path, label, blurb) in zip(cols, row):
            with col:
                st.page_link(path, label=label)
                st.caption(blurb)


def main() -> None:
    """Render the landing page."""
    reliability = load_line_reliability()
    selected, date_range = render_sidebar(reliability)

    theme.sign(
        "Transit Pulse",
        sub="NYC subway performance, 2015–present · SODA API → BigQuery → dbt → Streamlit",
        routes=HERO_ROUTES,
        hero=True,
    )
    st.markdown(
        "An end-to-end analytics platform for the New York City subway: on-time "
        "performance, delays and their causes, reliability modeling, and ridership "
        "recovery — with Great Expectations data-quality gates and CI/CD behind it."
    )
    st.write("")
    render_kpis(reliability, selected, date_range)
    st.divider()
    render_explore()


if __name__ == "__main__":
    main()
