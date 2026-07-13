"""Page 2 — Station delay map (visual centerpiece).

A Folium map of every station, colored by its primary line's reliability tier
and sized by ridership, with per-tier layer toggles and rich popups.
"""

from __future__ import annotations

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from folium.plugins import Fullscreen

import theme
from data import (
    TIER_COLORS,
    available_lines,
    load_station_performance,
)

theme.setup("Station Delay Map")

NYC_CENTER = (40.7128, -74.0060)

_TIER_LABEL = {
    "reliable": "Reliable (≥90% OTP)",
    "at_risk": "At risk (80–90% OTP)",
    "poor": "Poor (<80% OTP)",
    "unknown": "Unknown / shuttle",
}


def _radius(ridership: float | None) -> float:
    """Scale a marker radius from monthly ridership (sqrt for perceptual area).

    Args:
        ridership: Average monthly ridership, or None.

    Returns:
        A marker radius in pixels, clamped to a sensible range.
    """
    if ridership is None or pd.isna(ridership) or ridership <= 0:
        return 3.0
    return float(min(20.0, max(4.0, (ridership ** 0.5) / 40.0)))


def _popup_html(row: pd.Series) -> str:
    """Build the HTML popup for a station marker."""
    otp = f"{row['otp_pct']:.1f}%" if pd.notna(row["otp_pct"]) else "n/a"
    riders = f"{row['avg_monthly_ridership']:,.0f}" if pd.notna(row["avg_monthly_ridership"]) else "n/a"
    return (
        f"<div style='font-family:Helvetica,Arial,sans-serif;font-size:12.5px'>"
        f"<b style='font-size:13.5px'>{row['stop_name']}</b><br>"
        f"Borough: {row['borough']}<br>"
        f"Routes: {row['daytime_routes']}<br>"
        f"Primary line OTP: <b>{otp}</b><br>"
        f"Reliability: {row['reliability_tier'].replace('_', ' ')}<br>"
        f"Avg monthly ridership: {riders}</div>"
    )


@st.cache_data(ttl=3600)
def build_map_html(stations: pd.DataFrame) -> str:
    """Build the Folium map as an HTML string (cached on the input frame).

    Args:
        stations: The station-performance mart.

    Returns:
        Rendered map HTML for embedding.
    """
    fmap = folium.Map(location=NYC_CENTER, zoom_start=11, tiles="cartodbpositron")
    Fullscreen().add_to(fmap)

    layers = {
        tier: folium.FeatureGroup(name=_TIER_LABEL[tier], show=(tier != "unknown"))
        for tier in TIER_COLORS
    }
    for _, row in stations.iterrows():
        tier = row["reliability_tier"] if row["reliability_tier"] in TIER_COLORS else "unknown"
        folium.CircleMarker(
            location=(row["latitude"], row["longitude"]),
            radius=_radius(row["avg_monthly_ridership"]),
            color=TIER_COLORS[tier],
            fill=True,
            fill_color=TIER_COLORS[tier],
            fill_opacity=0.72,
            weight=1,
            popup=folium.Popup(_popup_html(row), max_width=260),
            tooltip=row["stop_name"],
        ).add_to(layers[tier])

    for layer in layers.values():
        layer.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap.get_root().render()


def main() -> None:
    """Render the station delay map page."""
    stations = load_station_performance()
    lines = st.session_state.get("selected_lines") or available_lines()
    view = stations[stations["primary_route"].isin(lines)] if lines else stations

    theme.sign(
        "Station delay map",
        sub=f"{len(view):,} stations · colored by the primary line's on-time tier, "
            "sized by average monthly ridership",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stations shown", f"{len(view):,}")
    c2.metric("Reliable", f"{(view['reliability_tier'] == 'reliable').sum():,}")
    c3.metric("At risk", f"{(view['reliability_tier'] == 'at_risk').sum():,}")
    c4.metric("Poor", f"{(view['reliability_tier'] == 'poor').sum():,}")
    st.write("")

    legend = " &nbsp; ".join(
        f"<span style='color:{TIER_COLORS[t]};font-size:15px'>●</span> "
        f"<span style='font-size:13px;color:#2A2D33'>{_TIER_LABEL[t]}</span>"
        for t in ("reliable", "at_risk", "poor", "unknown")
    )
    st.markdown(legend, unsafe_allow_html=True)
    st.write("")

    components.html(build_map_html(view), height=640)
    st.caption("Marker area is proportional to ridership. Click any station for details; "
               "toggle tiers with the layer control (top right).")


if __name__ == "__main__":
    main()
