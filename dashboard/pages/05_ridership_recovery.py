"""Page 5 — Ridership recovery: where the riders came back after the pandemic."""

from __future__ import annotations

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from branca.colormap import LinearColormap

from data import load_ridership_recovery

st.set_page_config(page_title="Ridership Recovery — Transit Pulse", page_icon="📉", layout="wide")

NYC_CENTER = (40.7128, -74.0060)


@st.cache_data(ttl=3600)
def build_recovery_map(stations: pd.DataFrame) -> str:
    """Build a Folium map colored by recovery percentage.

    Args:
        stations: The ridership-recovery mart (needs lat/long/recovery_pct).

    Returns:
        Rendered map HTML.
    """
    pts = stations.dropna(subset=["latitude", "longitude", "recovery_pct"])
    fmap = folium.Map(location=NYC_CENTER, zoom_start=11, tiles="cartodbpositron")
    cmap = LinearColormap(
        ["#b2182b", "#f4a582", "#f7f7f7", "#92c5de", "#2166ac"],
        vmin=40, vmax=120, caption="Ridership recovery vs 2019 (%)",
    )
    for _, r in pts.iterrows():
        pct = min(max(r["recovery_pct"], 40), 120)
        folium.CircleMarker(
            location=(r["latitude"], r["longitude"]),
            radius=5, color=None, fill=True, fill_color=cmap(pct), fill_opacity=0.85,
            popup=folium.Popup(
                f"<b>{r['station_complex']}</b><br>{r['borough']}<br>"
                f"Recovery: <b>{r['recovery_pct']:.0f}%</b> of 2019<br>"
                f"Now: {r['recent_ridership']:,.0f}/mo",
                max_width=240),
            tooltip=f"{r['station_complex']} — {r['recovery_pct']:.0f}%",
        ).add_to(fmap)
    cmap.add_to(fmap)
    return fmap.get_root().render()


def main() -> None:
    """Render the ridership-recovery page."""
    st.title("📉 Ridership Recovery")
    st.markdown(
        "Each station's trailing-12-month ridership against its **2019 pre-pandemic "
        "baseline**. Six years on, the recovery is real but uneven, and the gap falls "
        "along borough lines."
    )

    data = load_ridership_recovery()
    if data.empty:
        st.warning("No recovery data available.")
        return

    system = data["recent_ridership"].sum() / data["baseline_2019"].sum() * 100
    depressed = int((data["recovery_tier"] == "depressed").sum())
    recovered = int((data["recovery_tier"] == "fully_recovered").sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("System recovery", f"{system:.0f}%", "of 2019 ridership")
    c2.metric("Still depressed", f"{depressed}", "stations below 70%")
    c3.metric("Fully recovered", f"{recovered}", "stations at/above 2019")

    boro = (
        data.groupby("borough")
        .apply(lambda g: g["recent_ridership"].sum() / g["baseline_2019"].sum() * 100,
               include_groups=False)
        .sort_values(ascending=False)
    )
    st.subheader("Recovery by borough")
    st.bar_chart(boro, height=280, y_label="Recovery vs 2019 (%)")

    st.subheader("Station-level recovery map")
    st.caption("Blue is recovered or above 2019; red is still well below. Click any station.")
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
