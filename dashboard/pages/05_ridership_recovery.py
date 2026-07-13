"""Page 5 — Ridership recovery: where the riders came back after the pandemic."""

from __future__ import annotations

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from branca.colormap import LinearColormap

import theme
from data import load_ridership_recovery

theme.setup("Ridership Recovery")

NYC_CENTER = (40.7128, -74.0060)


@st.cache_data(ttl=3600)
def build_recovery_map(stations: pd.DataFrame) -> str:
    """Build a Folium map colored by recovery percentage.

    The scale is anchored so the neutral color sits at exactly 100% — a station
    that fully recovered reads as neutral, reds are still down, blues are above
    their 2019 baseline.

    Args:
        stations: The ridership-recovery mart (needs lat/long/recovery_pct).

    Returns:
        Rendered map HTML.
    """
    pts = stations.dropna(subset=["latitude", "longitude", "recovery_pct"])
    fmap = folium.Map(location=NYC_CENTER, zoom_start=11, tiles="cartodbpositron")
    cmap = LinearColormap(
        ["#b2182b", "#f4a582", "#f2f2ee", "#92c5de", "#2166ac"],
        index=[40, 70, 100, 110, 120],
        vmin=40, vmax=120, caption="Ridership recovery vs 2019 (%) — neutral = fully recovered",
    )
    for _, r in pts.iterrows():
        pct = min(max(r["recovery_pct"], 40), 120)
        folium.CircleMarker(
            location=(r["latitude"], r["longitude"]),
            radius=5, color="#9a9a94", weight=0.5, fill=True,
            fill_color=cmap(pct), fill_opacity=0.9,
            popup=folium.Popup(
                f"<div style='font-family:Helvetica,Arial,sans-serif;font-size:12.5px'>"
                f"<b>{r['station_complex']}</b><br>{r['borough']}<br>"
                f"Recovery: <b>{r['recovery_pct']:.0f}%</b> of 2019<br>"
                f"Now: {r['recent_ridership']:,.0f}/mo</div>",
                max_width=240),
            tooltip=f"{r['station_complex']} — {r['recovery_pct']:.0f}%",
        ).add_to(fmap)
    cmap.add_to(fmap)
    return fmap.get_root().render()


def main() -> None:
    """Render the ridership-recovery page."""
    data = load_ridership_recovery()
    if data.empty:
        theme.sign("Ridership recovery")
        st.warning("No recovery data available.")
        return

    system = data["recent_ridership"].sum() / data["baseline_2019"].sum() * 100
    depressed = int((data["recovery_tier"] == "depressed").sum())
    recovered = int((data["recovery_tier"] == "fully_recovered").sum())

    theme.sign(
        "Ridership recovery",
        sub="Trailing 12 months against each station's 2019 pre-pandemic baseline",
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("System recovery", f"{system:.0f}%", "of 2019 ridership")
    c2.metric("Still depressed", f"{depressed}", "stations below 70%")
    c3.metric("Fully recovered", f"{recovered}", "stations at/above 2019")
    st.write("")

    boro = (
        data.groupby("borough")
        .apply(lambda g: g["recent_ridership"].sum() / g["baseline_2019"].sum() * 100,
               include_groups=False)
        .sort_values(ascending=False)
        .round(1)
        .reset_index(name="recovery_pct")
    )
    st.subheader("Recovery by borough")
    st.caption("The gap falls along borough lines — the Bronx trails Queens by "
               "sixteen points.")
    fig_boro = px.bar(
        boro, x="borough", y="recovery_pct", text="recovery_pct",
        labels={"borough": "", "recovery_pct": "Recovery vs 2019 (%)"},
    )
    fig_boro.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                           marker_color=theme.CATEGORICAL[0], marker_line_width=0)
    fig_boro.update_layout(height=340, bargap=0.45, yaxis_range=[0, 100])
    st.plotly_chart(fig_boro, use_container_width=True)

    st.subheader("Station-level recovery map")
    st.caption("Neutral is exactly the 2019 level. Blue means above baseline; "
               "red means still well below. Click any station.")
    components.html(build_recovery_map(data), height=560)

    left, right = st.columns(2)
    with left:
        st.subheader("Weakest recovery")
        st.dataframe(
            data.nsmallest(8, "recovery_pct")[["station_complex", "borough", "recovery_pct"]],
            use_container_width=True, hide_index=True,
        )
    with right:
        st.subheader("Strongest recovery")
        st.dataframe(
            data.nlargest(8, "recovery_pct")[["station_complex", "borough", "recovery_pct"]],
            use_container_width=True, hide_index=True,
        )


if __name__ == "__main__":
    main()
