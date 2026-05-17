"""GSK-strict theme: Orange / White / Black / Grey only.

Single source of truth for the UI palette and global CSS. Import constants
where you need a colour; call `inject_css()` once in app.py.
"""
from __future__ import annotations
import streamlit as st

# ── PALETTE (the only colours allowed in the UI) ─────────────────────────
ORANGE        = "#F36633"   # GSK primary
ORANGE_LIGHT  = "#FF8A5C"   # hover / accent fill
ORANGE_DARK   = "#C4501F"   # pressed / strong text
ORANGE_TINT   = "#FFF1EA"   # very light wash for warning surfaces

WHITE         = "#FFFFFF"
OFFWHITE      = "#FAFAFA"
SURFACE       = "#F7F7F7"   # app background
SURFACE_2     = "#F2F2F2"   # cards / muted blocks
SURFACE_3     = "#EBEBEB"   # subtle dividers

GREY_LINE     = "#D8D8D8"   # borders
GREY_MUTED    = "#999999"   # placeholders
GREY_TEXT     = "#555555"   # secondary text
GREY_DARK     = "#333333"   # body
GREY_DEEP     = "#222222"   # heavy text on light

BLACK         = "#000000"
NEAR_BLACK    = "#1A1A1A"   # primary text


# ── SEMANTIC ROLES (mapped to the palette only) ──────────────────────────
# Risk badges
RISK_LOW_BG,     RISK_LOW_FG     = SURFACE_2, GREY_DARK
RISK_MEDIUM_BG,  RISK_MEDIUM_FG  = GREY_LINE, NEAR_BLACK
RISK_HIGH_BG,    RISK_HIGH_FG    = NEAR_BLACK, ORANGE
RISK_BLOCKED_BG, RISK_BLOCKED_FG = ORANGE,    WHITE

# Alerts (strict palette — no green/yellow/red)
ALERT_SUCCESS_BG, ALERT_SUCCESS_FG, ALERT_SUCCESS_BORDER = SURFACE_2, NEAR_BLACK, GREY_LINE
ALERT_WARNING_BG, ALERT_WARNING_FG, ALERT_WARNING_BORDER = WHITE,     ORANGE_DARK, ORANGE
ALERT_ERROR_BG,   ALERT_ERROR_FG,   ALERT_ERROR_BORDER   = NEAR_BLACK, ORANGE,     ORANGE
ALERT_INFO_BG,    ALERT_INFO_FG,    ALERT_INFO_BORDER    = SURFACE_2, GREY_DARK,   GREY_LINE


# ── GLOBAL CSS ───────────────────────────────────────────────────────────
_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=DM+Mono:wght@400;500&display=swap');

/* Force light theme */
html,body{{color-scheme:light!important;background:{SURFACE}!important;color:{NEAR_BLACK}!important;}}
html,body,[class*="css"]{{font-family:'EB Garamond',Georgia,'Times New Roman',serif;font-size:16px;}}
code,.stCode,pre{{font-family:'DM Mono',monospace;font-size:.92em;}}

/* App shell */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.block-container{{background:{SURFACE}!important;color:{NEAR_BLACK}!important;}}
section[data-testid="stSidebar"]{{background:{WHITE}!important;border-right:1px solid {GREY_LINE}!important;color:{NEAR_BLACK}!important;}}
section[data-testid="stSidebar"] *{{color:{NEAR_BLACK}!important;}}
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{{color:{GREY_MUTED}!important;}}

/* Markdown / text */
.stMarkdown, [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] em,
[data-testid="stText"], p{{color:{NEAR_BLACK}!important;}}

/* Header card */
.nexus-header{{
  background:{WHITE};
  border:1px solid {GREY_LINE};
  border-left:4px solid {ORANGE};
  border-radius:10px;
  padding:1.4rem 2rem;
  margin-bottom:1.2rem;
  position:relative;
  overflow:hidden;
}}
.nexus-header::before{{
  content:"";position:absolute;inset:0;
  background:radial-gradient(ellipse at 80% 50%,rgba(243,102,51,.05) 0%,transparent 65%);
  pointer-events:none;
}}
.nexus-title{{font-size:1.85rem;font-weight:600;color:{NEAR_BLACK}!important;margin:0;line-height:1.2;letter-spacing:-0.01em;font-style:italic;}}
.nexus-title span{{color:{ORANGE}!important;font-style:normal;}}
.nexus-sub{{color:{GREY_TEXT}!important;font-size:.88rem;margin:.3rem 0 0;font-weight:400;letter-spacing:.02em;}}

.nexus-status{{display:inline-flex;align-items:center;gap:.4rem;font-size:.78rem;color:{GREY_TEXT}!important;}}
.nexus-status-dot{{width:8px;height:8px;border-radius:50%;display:inline-block;}}
.nexus-status-dot.on{{background:{ORANGE};box-shadow:0 0 0 3px rgba(243,102,51,.15);}}
.nexus-status-dot.off{{background:{GREY_LINE};}}

/* Plan / info cards */
.plan-card{{background:{WHITE};border:1px solid {GREY_LINE};border-top:3px solid {ORANGE};border-radius:8px;padding:1rem 1.2rem;margin:.6rem 0;}}
.plan-label{{font-size:.72rem;font-weight:600;letter-spacing:.08em;color:{ORANGE}!important;text-transform:uppercase;margin-bottom:.3rem;}}
.plan-value{{font-size:.85rem;color:{GREY_DARK}!important;}}
.plan-tag{{display:inline-block;background:{SURFACE_2};border:1px solid {GREY_LINE};border-radius:4px;padding:.15rem .5rem;font-size:.75rem;color:{GREY_DARK}!important;margin:.15rem .15rem 0 0;font-family:'DM Mono',monospace;}}
.plan-warn{{background:{ORANGE_TINT};border:1px solid {ORANGE_LIGHT};border-radius:6px;padding:.6rem .8rem;margin-top:.5rem;font-size:.8rem;color:{ORANGE_DARK}!important;}}

/* Risk badges (strict palette) */
.risk-low{{background:{RISK_LOW_BG};color:{RISK_LOW_FG}!important;border:1px solid {GREY_LINE};border-radius:4px;padding:.1rem .5rem;font-size:.72rem;font-weight:600;}}
.risk-medium{{background:{RISK_MEDIUM_BG};color:{RISK_MEDIUM_FG}!important;border:1px solid {GREY_LINE};border-radius:4px;padding:.1rem .5rem;font-size:.72rem;font-weight:600;}}
.risk-high{{background:{RISK_HIGH_BG};color:{RISK_HIGH_FG}!important;border:1px solid {NEAR_BLACK};border-radius:4px;padding:.1rem .5rem;font-size:.72rem;font-weight:600;}}
.risk-blocked{{background:{RISK_BLOCKED_BG};color:{RISK_BLOCKED_FG}!important;border:1px solid {ORANGE_DARK};border-radius:4px;padding:.1rem .5rem;font-size:.72rem;font-weight:600;}}

/* Generic chip */
.chip{{display:inline-flex;align-items:center;gap:.3rem;background:{SURFACE_2};border:1px solid {GREY_LINE};border-radius:4px;padding:.15rem .55rem;font-size:.75rem;color:{GREY_DARK}!important;}}
.chip-orange{{background:{WHITE};border-color:{ORANGE};color:{ORANGE_DARK}!important;}}
.chip-dark{{background:{NEAR_BLACK};border-color:{NEAR_BLACK};color:{ORANGE}!important;}}

/* Confidence bar */
.confidence-bar{{height:4px;border-radius:2px;background:linear-gradient(90deg,{ORANGE},{ORANGE_LIGHT});margin-top:4px;}}

/* Expander */
details summary{{color:{GREY_TEXT}!important;font-size:.8rem!important;}}
details[open] summary{{color:{ORANGE}!important;}}
[data-testid="stExpander"]{{background:{WHITE}!important;border:1px solid {GREY_LINE}!important;}}
[data-testid="stExpanderDetails"]{{background:{WHITE}!important;color:{NEAR_BLACK}!important;}}
[data-testid="stExpanderDetails"] *{{color:{NEAR_BLACK};}}

/* Chat */
.stChatInput>div{{background:{WHITE}!important;border-color:{GREY_LINE}!important;}}
.stChatInput textarea{{color:{NEAR_BLACK}!important;background:{WHITE}!important;}}
.stChatInput textarea::placeholder{{color:{GREY_MUTED}!important;}}
[data-testid="stChatMessage"]{{background:{WHITE}!important;border:1px solid {SURFACE_3}!important;border-radius:8px!important;}}
[data-testid="stChatMessageContent"], [data-testid="stChatMessageContent"] p, [data-testid="stChatMessageContent"] *{{color:{NEAR_BLACK}!important;}}

/* Alerts (strict palette) */
[data-testid="stAlert"]{{color:{NEAR_BLACK}!important;border-radius:6px!important;}}
[data-testid="stAlert"] p{{color:inherit!important;}}
.stSuccess{{background:{ALERT_SUCCESS_BG}!important;color:{ALERT_SUCCESS_FG}!important;border:1px solid {ALERT_SUCCESS_BORDER}!important;}}
.stWarning{{background:{ALERT_WARNING_BG}!important;color:{ALERT_WARNING_FG}!important;border:1px solid {ALERT_WARNING_BORDER}!important;}}
.stError{{background:{ALERT_ERROR_BG}!important;color:{ALERT_ERROR_FG}!important;border:1px solid {ALERT_ERROR_BORDER}!important;}}
.stError *{{color:{ALERT_ERROR_FG}!important;}}
.stInfo{{background:{ALERT_INFO_BG}!important;color:{ALERT_INFO_FG}!important;border:1px solid {ALERT_INFO_BORDER}!important;}}

/* Spinner */
[data-testid="stSpinner"] p{{color:{GREY_TEXT}!important;}}
.stSpinner>div>div{{border-top-color:{ORANGE}!important;}}

/* Buttons */
.stButton>button{{background:{WHITE}!important;border:1px solid {GREY_LINE}!important;color:{GREY_DARK}!important;border-radius:6px!important;font-size:.92rem!important;font-family:'EB Garamond',Georgia,serif!important;letter-spacing:.01em!important;transition:all .15s!important;}}
.stButton>button:hover{{border-color:{ORANGE}!important;color:{ORANGE}!important;background:{WHITE}!important;}}
.stButton>button:focus,.stButton>button:active{{background:{ORANGE}!important;color:{WHITE}!important;border-color:{ORANGE}!important;box-shadow:none!important;}}
.stButton>button[kind="primary"]{{background:{ORANGE}!important;color:{WHITE}!important;border-color:{ORANGE}!important;}}
.stButton>button[kind="primary"]:hover{{background:{ORANGE_DARK}!important;border-color:{ORANGE_DARK}!important;}}

/* Inputs */
.stTextInput>div>div>input,
.stTextArea textarea,
.stSelectbox>div>div,
.stNumberInput input{{background:{WHITE}!important;border-color:{GREY_LINE}!important;color:{NEAR_BLACK}!important;}}
.stTextInput>div>div>input:focus,
.stTextArea textarea:focus{{border-color:{ORANGE}!important;box-shadow:0 0 0 1px {ORANGE}!important;}}

/* Tabs */
[data-baseweb="tab-list"]{{gap:.25rem;border-bottom:1px solid {GREY_LINE}!important;}}
[data-baseweb="tab"]{{
  background:transparent!important;
  color:{GREY_TEXT}!important;
  border-bottom:2px solid transparent!important;
  padding:.55rem .9rem!important;
  font-size:.95rem!important;
  font-weight:500!important;
  font-family:'EB Garamond',Georgia,serif!important;
  transition:color .15s, border-color .15s;
}}
[data-baseweb="tab"]:hover{{color:{NEAR_BLACK}!important;background:{SURFACE_2}!important;}}
[data-baseweb="tab"][aria-selected="true"]{{
  color:{ORANGE}!important;
  border-bottom-color:{ORANGE}!important;
  font-weight:600!important;
}}
[data-baseweb="tab"] svg, [data-baseweb="tab"] [data-testid="stIconMaterial"]{{color:inherit!important;}}

/* Metrics */
[data-testid="stMetric"]{{background:{WHITE};border:1px solid {GREY_LINE};border-radius:8px;padding:.8rem 1rem;}}
[data-testid="stMetricLabel"]{{color:{GREY_TEXT}!important;font-size:.78rem!important;text-transform:uppercase;letter-spacing:.08em;font-family:'EB Garamond',Georgia,serif!important;}}
[data-testid="stMetricValue"]{{color:{NEAR_BLACK}!important;font-weight:600!important;font-size:1.6rem!important;}}
[data-testid="stMetricDelta"] svg{{display:none;}}
[data-testid="stMetricDelta"]{{color:{ORANGE}!important;}}

/* Dataframe */
[data-testid="stDataFrame"]{{border:1px solid {GREY_LINE};border-radius:6px;}}

/* Section heading */
.nx-section{{display:flex;align-items:center;gap:.5rem;font-size:.72rem;font-weight:600;letter-spacing:.1em;color:{ORANGE}!important;text-transform:uppercase;margin:1.4rem 0 .6rem;}}
.nx-section::after{{content:"";flex:1;height:1px;background:{GREY_LINE};margin-left:.4rem;}}

/* Inline icon helpers */
.nx-icon{{display:inline-flex;vertical-align:middle;line-height:0;}}
.nx-icon svg{{display:block;}}
</style>
"""


def inject_css() -> None:
    """Inject the global stylesheet. Call once in app.py before any UI."""
    st.markdown(_CSS, unsafe_allow_html=True)
