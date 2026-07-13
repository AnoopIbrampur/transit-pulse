"""Page 4 — Delay root causes: what makes trains late, and how it has shifted."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data import available_lines, load_delay_causes

st.set_page_config(page_title="Delay Causes — Transit Pulse", page_icon="🧯", layout="wide")

# Consistent color per cause across the page.
CAUSE_COLORS = {
    "Infrastructure & Equipment": "#e74c3c",
    "Police & Medical": "#8e44ad",
    "Planned ROW Work": "#e67e22",
    "Crew Availability": "#2980b9",
    "Operating Conditions": "#16a085",
    "External Factors": "#7f8c8d",
}


def main() -> None:
    """Render the delay-causes page."""
    st.title("🧯 Delay Root Causes")
    st.markdown(
        "The MTA tags every delay with a cause. This is the part of the data that "
        "explains *why* the network runs late, and the mix has changed over time. "
        "Delay-cause data starts in 2020."
    )

    data = load_delay_causes()
    lines = st.session_state.get("selected_lines") or available_lines()
    data = data[data["line_name"].isin(lines)] if lines else data
    if data.empty:
        st.warning("No data for the current filters.")
        return

    data["period"] = pd.to_datetime(data["period"])

    # Systemwide totals by cause over the whole window.
    totals = (
        data.groupby("reporting_category", as_index=False)["delays"].sum()
        .sort_values("delays", ascending=True)
    )
    total_delays = int(totals["delays"].sum())
    top_cause = totals.iloc[-1]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total delays (2020+)", f"{total_delays:,}")
    c2.metric("Biggest cause", top_cause["reporting_category"],
              f"{top_cause['delays'] / total_delays * 100:.0f}% of all delays")
    c3.metric("Cause categories", f"{data['reporting_category'].nunique()}")

    st.subheader("Total delays by cause")
    fig_bar = px.bar(
        totals, x="delays", y="reporting_category", orientation="h",
        color="reporting_category", color_discrete_map=CAUSE_COLORS,
        labels={"delays": "Total delays", "reporting_category": "Cause"},
    )
    fig_bar.update_layout(height=340, showlegend=False, yaxis_title=None)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("How the mix of causes has shifted")
    st.caption(
        "Share of each month's delays by cause. Infrastructure & Equipment has grown "
        "as a share since 2020; crew and operating-condition delays have shrunk."
    )
    monthly = (
        data.groupby(["period", "reporting_category"], as_index=False)["delays"].sum()
    )
    monthly["share"] = monthly.groupby("period")["delays"].transform(
        lambda s: s / s.sum() * 100
    )
    fig_area = px.area(
        monthly.sort_values("period"),
        x="period", y="share", color="reporting_category",
        color_discrete_map=CAUSE_COLORS,
        labels={"share": "Share of delays (%)", "period": "Month",
                "reporting_category": "Cause"},
    )
    fig_area.update_layout(height=440, hovermode="x unified", legend_title_text="Cause",
                           yaxis_range=[0, 100])
    st.plotly_chart(fig_area, use_container_width=True)

    with st.expander("Cause totals table"):
        st.dataframe(
            totals.sort_values("delays", ascending=False)
            .assign(pct=lambda d: (d["delays"] / total_delays * 100).round(1)),
            use_container_width=True, hide_index=True,
        )


if __name__ == "__main__":
    main()
