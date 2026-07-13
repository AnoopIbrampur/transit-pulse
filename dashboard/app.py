"""Transit Pulse — NYC MTA subway analytics dashboard (Streamlit entry point).

This is the landing page: a short intro, headline KPIs, and the global sidebar
filters (line multiselect + date range) that every page reads from
``st.session_state``.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data import (
    available_lines,
    filter_by_lines_and_dates,
    load_line_reliability,
)

st.set_page_config(
    page_title="Transit Pulse — NYC MTA Analytics",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_sidebar(reliability: pd.DataFrame) -> tuple[list[str], tuple]:
    """Render the global sidebar filters and persist them in session state.

    Args:
        reliability: The line-reliability mart (drives filter bounds).

    Returns:
        (selected_lines, (start_date, end_date)) — also stored in session_state.
    """
    st.sidebar.title("🚇 Transit Pulse")
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
    c1.metric("Avg on-time performance", f"{avg_otp:.1f}%")
    c2.metric("Avg line health score", f"{avg_health:.1f}")
    c3.metric("Monthly passengers", f"{total_riders/1e6:.1f}M")
    c4.metric(
        "Worst line (OTP)",
        f"{worst_row['line_name']}",
        f"{worst_row['otp_pct']:.1f}%",
        delta_color="inverse",
    )
    st.caption(f"KPIs reflect the latest month in range: {pd.to_datetime(latest_period):%B %Y}")


def main() -> None:
    """Render the landing page."""
    reliability = load_line_reliability()
    selected, date_range = render_sidebar(reliability)

    st.title("Transit Pulse 🚇")
    st.markdown(
        "**An end-to-end analytics platform for NYC subway performance.** "
        "Explore on-time performance, delays, reliability, and ridership across "
        "every line — powered by an ELT pipeline (SODA API → BigQuery → dbt) with "
        "Great Expectations data-quality gates and CI/CD."
    )
    st.divider()
    render_kpis(reliability, selected, date_range)
    st.divider()

    st.subheader("Explore")
    a, b, c = st.columns(3)
    a.markdown("#### 📊 Line Performance\nOTP rankings and trends by line.")
    b.markdown("#### 🗺️ Station Delay Map\nGeospatial reliability across the network.")
    c.markdown("#### 📈 Time Trends\nSeasonality, peak vs off-peak, year-over-year.")
    d, e, f = st.columns(3)
    d.markdown("#### 🧯 Delay Causes\nWhat makes trains late, and how the mix shifted.")
    e.markdown("#### 📉 Ridership Recovery\nPost-pandemic recovery by station and borough.")
    f.markdown("#### 🔬 Insights\nDriver regression, forecasting, anomaly detection.")
    st.caption("Use the pages in the sidebar to dive in.")


if __name__ == "__main__":
    main()
