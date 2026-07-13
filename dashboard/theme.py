"""Design system for the Transit Pulse dashboard.

The visual language borrows from the thing being measured: NYC subway signage.
Helvetica, black station-sign bars with white text, official MTA route-bullet
colors, and a paper-white content area with card surfaces. One module owns every
token so the seven pages stay consistent.

Color assignment follows the chart's job:
- route identity  -> official MTA route colors (domain-anchored, fixed per entity)
- reliability     -> a reserved status trio (good/warning/critical) + text labels
- cause categories-> a fixed-order categorical palette (validated slot order)
- polarity        -> a blue/red diverging pair around a neutral gray
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------- tokens

INK = "#14161A"
INK_SOFT = "#5C6068"
PAPER = "#F6F6F3"          # app ground: warm off-white, like station tile
CARD = "#FFFFFF"
HAIR = "#E4E4DE"
SIGN_BLACK = "#101318"     # station-sign black (sidebar, section signs)
MTA_BLUE = "#0039A6"       # accent / active page

# Status trio (reserved for reliability tiers, always shown with text labels).
GOOD = "#00933C"
WARN = "#C77F00"
BAD = "#EE352E"
NEUTRAL = "#808183"

TIER_COLORS: dict[str, str] = {
    "reliable": GOOD,
    "at_risk": WARN,
    "poor": BAD,
    "unknown": NEUTRAL,
}

# Fixed-order categorical palette (pre-validated slot order; do not re-sort).
CATEGORICAL: list[str] = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]

# Diverging pair for polarity (regression coefficients, above/below baseline).
DIVERGE_POS = "#2a78d6"
DIVERGE_NEG = "#e34948"
DIVERGE_MID = "#ECECE4"

# Delay causes: fixed assignment in stacking order (largest first).
CAUSE_ORDER: list[str] = [
    "Infrastructure & Equipment",
    "Police & Medical",
    "Planned ROW Work",
    "Crew Availability",
    "Operating Conditions",
    "External Factors",
]
CAUSE_COLORS: dict[str, str] = dict(zip(CAUSE_ORDER, CATEGORICAL))

# Official MTA route colors (domain-anchored identity).
ROUTE_COLORS: dict[str, str] = {
    "1": "#EE352E", "2": "#EE352E", "3": "#EE352E",
    "4": "#00933C", "5": "#00933C", "6": "#00933C",
    "7": "#B933AD",
    "A": "#0039A6", "C": "#0039A6", "E": "#0039A6",
    "B": "#FF6319", "D": "#FF6319", "F": "#FF6319", "M": "#FF6319",
    "G": "#6CBE45",
    "J": "#996633", "Z": "#996633", "JZ": "#996633",
    "L": "#A7A9AC",
    "N": "#FCCC0A", "Q": "#FCCC0A", "R": "#FCCC0A", "W": "#FCCC0A",
    "S": "#808183", "FS": "#808183", "GS": "#808183", "H": "#808183",
    "S 42nd": "#808183", "S Fkln": "#808183", "S Rock": "#808183",
}
_DARK_TEXT_ROUTES = {"N", "Q", "R", "W", "L"}

FONT_STACK = '"Helvetica Neue", Helvetica, Arial, "Liberation Sans", sans-serif'


def route_color(line: str) -> str:
    """Return the official color for a route code, gray if unknown."""
    return ROUTE_COLORS.get(line, NEUTRAL)


# ---------------------------------------------------------------- plotly template

def _register_template() -> None:
    """Register and default the shared Plotly template."""
    axis = dict(gridcolor="#ECECE6", zerolinecolor="#DCDCD4", linecolor="#DCDCD4", ticks="")
    pio.templates["transit"] = go.layout.Template(
        layout=dict(
            font=dict(family=FONT_STACK, size=13, color=INK),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=CATEGORICAL,
            xaxis=axis,
            yaxis=axis,
            margin=dict(t=44, r=16, b=44, l=56),
            legend=dict(borderwidth=0, font=dict(size=12)),
            hoverlabel=dict(
                bgcolor=SIGN_BLACK, font=dict(family=FONT_STACK, size=12, color="#FFFFFF"),
                bordercolor=SIGN_BLACK,
            ),
        )
    )
    pio.templates.default = "transit"


# ---------------------------------------------------------------- CSS

_CSS = f"""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
    font-family: {FONT_STACK};
}}
.stApp {{ background: {PAPER}; }}
h1, h2, h3 {{
    font-family: {FONT_STACK};
    letter-spacing: -0.015em;
    color: {INK};
    font-weight: 800;
}}
[data-testid="stMarkdownContainer"] p {{ color: #2A2D33; }}
[data-testid="stCaptionContainer"] p, small {{ color: {INK_SOFT}; }}

/* chrome */
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"], #MainMenu {{ display: none; }}

/* station-sign section headers */
.mta-sign {{
    background: {SIGN_BLACK};
    border-radius: 10px;
    padding: 18px 22px;
    margin: 2px 0 18px;
    display: flex; align-items: center; justify-content: space-between;
    gap: 18px; flex-wrap: wrap;
}}
.mta-sign-title {{
    color: #FFFFFF; font-size: 28px; font-weight: 800;
    letter-spacing: -0.01em; line-height: 1.05;
}}
.mta-sign--hero .mta-sign-title {{ font-size: 38px; }}
.mta-sign-sub {{ color: #B9BEC7; font-size: 13px; margin-top: 5px; font-weight: 500; }}
.mta-bullets {{ display: flex; gap: 6px; flex-wrap: wrap; max-width: 460px; justify-content: flex-end; }}
.rb {{
    display: inline-grid; place-items: center; border-radius: 50%;
    font-weight: 800; font-family: {FONT_STACK}; flex: none;
    color: #FFFFFF; user-select: none;
}}

/* KPI cards */
[data-testid="stMetric"] {{
    background: {CARD}; border: 1px solid {HAIR}; border-radius: 12px;
    padding: 16px 18px 13px; box-shadow: 0 1px 2px rgba(16,19,24,.05);
}}
[data-testid="stMetricLabel"] p {{
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: .08em;
    font-weight: 700; color: {INK_SOFT};
}}
[data-testid="stMetricValue"] {{
    font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.02em;
}}

/* chart, table, iframe, expander surfaces */
[data-testid="stPlotlyChart"] {{
    background: {CARD}; border: 1px solid {HAIR}; border-radius: 12px;
    padding: 12px 12px 4px; box-shadow: 0 1px 2px rgba(16,19,24,.05);
}}
[data-testid="stDataFrame"] {{
    background: {CARD}; border: 1px solid {HAIR}; border-radius: 12px; padding: 6px;
}}
.stApp iframe {{ border: 1px solid {HAIR}; border-radius: 12px; background: {CARD}; }}
div[data-testid="stExpander"] details {{
    background: {CARD}; border: 1px solid {HAIR}; border-radius: 12px;
}}

/* page-link cards on the landing page */
[data-testid="stPageLink"] a {{
    display: block; background: {CARD}; border: 1px solid {HAIR};
    border-radius: 12px; padding: 14px 16px; text-decoration: none;
}}
[data-testid="stPageLink"] a:hover {{ border-color: {MTA_BLUE}; }}
[data-testid="stPageLink"] a p {{ font-weight: 700; color: {INK} !important; font-size: 1rem; }}

/* dark station-sign sidebar */
[data-testid="stSidebar"] {{
    background: {SIGN_BLACK};
    border-right: 1px solid #23272E;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li,
[data-testid="stSidebar"] label p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    color: #D7DBE2;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    color: #FFFFFF;
}}
[data-testid="stSidebar"] a {{ color: #8FB0FF; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: #9AA1AB; }}
[data-testid="stSidebar"] hr {{ border-color: #262B33; }}
[data-testid="stSidebarNav"] span {{ color: #D7DBE2; }}
[data-testid="stSidebarNav"] li a {{ border-radius: 8px; }}
[data-testid="stSidebarNav"] li a:hover {{ background: #1A1F26; }}
[data-testid="stSidebarNav"] li a[aria-current="page"] {{ background: {MTA_BLUE}; }}
[data-testid="stSidebarNav"] li a[aria-current="page"] span {{ color: #FFFFFF; font-weight: 700; }}
[data-testid="stSidebar"] [data-baseweb="tag"] {{
    background: #1C2129; border: 1px solid #333A44;
}}
[data-testid="stSidebar"] [data-baseweb="tag"] span {{ color: #F2F4F7; }}
[data-testid="stSidebar"] [data-baseweb="tag"] svg {{ fill: #9AA1AB; }}
[data-testid="stSidebar"] [data-testid="stSliderThumbValue"] {{ color: #8FB0FF; }}
[data-testid="stSidebar"] [data-testid="stTickBarMin"],
[data-testid="stSidebar"] [data-testid="stTickBarMax"] {{ color: #9AA1AB; }}
</style>
"""


# ---------------------------------------------------------------- components

def bullet(route: str, size: int = 26) -> str:
    """Return HTML for one MTA-style route bullet."""
    color = route_color(route)
    text = "#14161A" if route in _DARK_TEXT_ROUTES else "#FFFFFF"
    label = "S" if route.startswith("S ") else route
    font = max(10, int(size * (0.5 if len(label) > 1 else 0.56)))
    return (
        f'<span class="rb" style="width:{size}px;height:{size}px;'
        f'background:{color};color:{text};font-size:{font}px">{label}</span>'
    )


def bullet_strip(routes: list[str], size: int = 26) -> str:
    """Return HTML for a row of route bullets."""
    return '<div class="mta-bullets">' + "".join(bullet(r, size) for r in routes) + "</div>"


def sign(title: str, sub: str | None = None, routes: list[str] | None = None,
         hero: bool = False) -> None:
    """Render a black station-sign header bar.

    Args:
        title: Main sign text.
        sub: Optional smaller line under the title.
        routes: Optional route codes rendered as bullets on the right.
        hero: Larger treatment for the landing page.
    """
    sub_html = f'<div class="mta-sign-sub">{sub}</div>' if sub else ""
    bullets = bullet_strip(routes, 30 if hero else 24) if routes else ""
    cls = "mta-sign mta-sign--hero" if hero else "mta-sign"
    st.markdown(
        f'<div class="{cls}"><div><div class="mta-sign-title">{title}</div>{sub_html}</div>'
        f"{bullets}</div>",
        unsafe_allow_html=True,
    )


def setup(page_title: str) -> None:
    """Per-page bootstrap: page config, CSS, and the Plotly template.

    Call once at the top of every page, before any other Streamlit call.
    """
    st.set_page_config(
        page_title=f"{page_title} — Transit Pulse",
        page_icon="🚇",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    _register_template()
