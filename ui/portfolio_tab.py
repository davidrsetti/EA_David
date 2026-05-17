"""
ui/portfolio_tab.py — Portfolio Intelligence Tab (QW-1)

Exposes the fully-built APM TIME model engine (core/apm_agent.py) in the UI.
Shows a live Gartner TIME quadrant, portfolio health score, sortable app table,
and prioritised Quick Wins — all scored automatically from the live knowledge graph.
"""
from __future__ import annotations
import streamlit as st

from nexus.ui.theme import (
    ORANGE, ORANGE_DARK, ORANGE_LIGHT, NEAR_BLACK, WHITE,
    GREY_TEXT, GREY_DARK, GREY_LINE, GREY_MUTED, SURFACE_2, SURFACE,
)
from nexus.ui.icons import icon, mat


# Strict palette: depth-of-orange-or-grey encodes TIME class.
_TIME_COLOUR = {
    "Invest":    ORANGE,        # primary action — keep / grow
    "Tolerate":  GREY_DARK,     # neutral — leave alone
    "Migrate":   ORANGE_LIGHT,  # secondary action — modernise
    "Eliminate": NEAR_BLACK,    # decisive — kill
}
# Material icon shortcodes for TIME quadrants (used in metric labels & legend).
_TIME_ICON = {
    "Invest":    mat("trending_up"),
    "Tolerate":  mat("pause"),
    "Migrate":   mat("sync_alt"),
    "Eliminate": mat("close"),
}
_TIME_DESC = {
    "Invest":    "Strategic priority — increase capability, modernise, expand.",
    "Tolerate":  "Keep running, minimal investment. Acceptable fit, low strategic value.",
    "Migrate":   "Good business value but poor technical fit. Re-platform or replace.",
    "Eliminate": "Low value, poor fit. Plan decommission, migrate dependent capabilities.",
}


def _health_colour(score: int) -> str:
    if score >= 75:
        return NEAR_BLACK
    if score >= 50:
        return GREY_DARK
    return ORANGE_DARK


def _health_label(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Fair"
    if score >= 40:
        return "At Risk"
    return "Critical"


def render_portfolio_tab(connected: bool, user_role: str) -> None:
    """Render the Portfolio Intelligence tab."""
    st.markdown(
        f"""
        <div style="border-left:4px solid {ORANGE};padding-left:1rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:.8rem">
          <span>{icon("bar-chart", size=26, color=ORANGE)}</span>
          <div>
            <h2 style="margin:0;font-size:1.4rem;color:{NEAR_BLACK}">Application Portfolio Intelligence</h2>
            <p style="margin:.25rem 0 0;color:{GREY_TEXT};font-size:.9rem">
              Gartner TIME model scoring — automatically computed from live graph data:
              capabilities, dependencies, findings, and lifecycle signals.
            </p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not connected:
        st.info("Connect to Stardog in the sidebar to run portfolio analysis.")
        return

    # ── Controls ──────────────────────────────────────────────────────────────
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])
    with col_ctrl1:
        domain_filter = st.text_input(
            "Domain filter (optional)",
            value="",
            placeholder="e.g. finance, HR, supply chain — leave blank for all",
            key="portfolio_domain_filter",
        )
    with col_ctrl2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button(f"{mat('bolt')}  Analyse Portfolio", key="portfolio_run", type="primary")
    with col_ctrl3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"{mat('refresh')}  Clear", key="portfolio_clear"):
            for k in list(st.session_state.keys()):
                if k.startswith("portfolio_result"):
                    del st.session_state[k]
            st.rerun()

    # ── Run analysis ──────────────────────────────────────────────────────────
    if run_btn or "portfolio_result" in st.session_state:
        if run_btn:
            with st.spinner("Scoring portfolio across capabilities, dependencies, and findings…"):
                try:
                    from nexus.core.apm_agent import run_apm_agent
                    result = run_apm_agent(focus_domain=domain_filter.strip(), user_role=user_role)
                    st.session_state["portfolio_result"] = result
                except Exception as exc:
                    st.error(f"Portfolio analysis failed: {exc}")
                    return

        result = st.session_state.get("portfolio_result")
        if result is None:
            return

        if result.error:
            st.warning(f"Analysis completed with warnings: {result.error}")

        _render_health_strip(result)
        st.markdown("---")
        _render_time_quadrant(result)
        st.markdown("---")
        _render_quick_wins(result)
        st.markdown("---")
        _render_app_table(result)
        if result.rationalisations:
            st.markdown("---")
            _render_rationalisations(result)


def _render_health_strip(result) -> None:
    """Five top-level metrics."""
    hc = _health_colour(result.portfolio_health)
    hl = _health_label(result.portfolio_health)

    st.markdown(
        f"""
        <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:.5rem">
          <div style="background:{WHITE};border:1px solid {GREY_LINE};border-radius:8px;
                      padding:1rem 1.5rem;min-width:140px;border-top:4px solid {hc}">
            <div style="font-size:2rem;font-weight:700;color:{hc}">{result.portfolio_health}</div>
            <div style="font-size:.75rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:.05em">
              Portfolio Health</div>
            <div style="font-size:.8rem;color:{hc};font-weight:600">{hl}</div>
          </div>
        """,
        unsafe_allow_html=True,
    )
    for tc, count in result.time_summary.items():
        colour = _TIME_COLOUR.get(tc, GREY_TEXT)
        tc_icon = _TIME_ICON.get(tc, mat("circle"))
        st.markdown(
            f"""
          <div style="background:{WHITE};border:1px solid {GREY_LINE};border-radius:8px;
                      padding:1rem 1.5rem;min-width:120px;border-top:4px solid {colour}">
            <div style="font-size:2rem;font-weight:700;color:{colour}">{count}</div>
            <div style="font-size:.75rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:.05em">
              {tc_icon} {tc}</div>
          </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    # Executive summary
    if result.executive_summary:
        with st.expander("Executive Summary", expanded=False):
            st.markdown(result.executive_summary)
    if result.investment_themes:
        with st.expander("Investment Themes", expanded=False):
            for t in result.investment_themes:
                st.markdown(f"- {t}")


def _render_time_quadrant(result) -> None:
    """Scatter plot of Business Value vs Technical Fit coloured by TIME class."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.warning("Install `plotly` to enable the TIME quadrant chart: `pip install plotly`")
        return

    if not result.app_scores:
        st.info("No applications scored.")
        return

    st.markdown("### TIME Quadrant")
    fig = go.Figure()

    for tc, colour in _TIME_COLOUR.items():
        apps = [s for s in result.app_scores if s.time_class.value == tc]
        if not apps:
            continue
        fig.add_trace(go.Scatter(
            x=[s.technical_fit for s in apps],
            y=[s.business_value for s in apps],
            mode="markers+text",
            name=tc,
            marker=dict(color=colour, size=12, opacity=0.85,
                        line=dict(color=WHITE, width=1)),
            text=[s.app_label for s in apps],
            textposition="top center",
            textfont=dict(size=9, color=NEAR_BLACK),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Technical Fit: %{x:.1f}<br>"
                "Business Value: %{y:.1f}<br>"
                "<extra></extra>"
            ),
            customdata=[[s.rationale, s.lifecycle, s.owner] for s in apps],
        ))

    # Quadrant lines
    fig.add_hline(y=4.0, line_dash="dash", line_color=GREY_LINE, line_width=1)
    fig.add_vline(x=5.0, line_dash="dash", line_color=GREY_LINE, line_width=1)

    # Quadrant labels
    for (x, y, label) in [
        (2.5, 7.5, "MIGRATE"), (7.5, 7.5, "INVEST"),
        (2.5, 2.0, "ELIMINATE"), (7.5, 2.0, "TOLERATE"),
    ]:
        fig.add_annotation(
            x=x, y=y, text=label,
            showarrow=False,
            font=dict(size=10, color=GREY_LINE),
            opacity=0.7,
        )

    fig.update_layout(
        xaxis_title="Technical Fit →",
        yaxis_title="Business Value →",
        xaxis=dict(range=[0, 10.5], gridcolor=SURFACE_2),
        yaxis=dict(range=[0, 10.5], gridcolor=SURFACE_2),
        plot_bgcolor=SURFACE,
        paper_bgcolor=WHITE,
        legend=dict(orientation="h", y=-0.15, font=dict(color=NEAR_BLACK)),
        font=dict(color=NEAR_BLACK),
        margin=dict(l=40, r=20, t=20, b=60),
        height=480,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_quick_wins(result) -> None:
    """Highlight quick win opportunities."""
    if not result.quick_wins:
        return
    st.markdown(f"<div class='nx-section'>{icon('zap', size=14, color=ORANGE)} Quick Wins</div>", unsafe_allow_html=True)
    cols = st.columns(min(3, len(result.quick_wins)))
    for i, qw in enumerate(result.quick_wins[:6]):
        with cols[i % 3]:
            st.markdown(
                f"""<div style="background:{WHITE};border:1px solid {GREY_LINE};border-left:3px solid {ORANGE};border-radius:8px;
                               padding:.75rem 1rem;font-size:.85rem;color:{NEAR_BLACK};display:flex;gap:.5rem;align-items:flex-start">
                  <span style="color:{ORANGE};flex-shrink:0">{icon('check-circle', size=16, color=ORANGE)}</span>
                  <span>{qw}</span>
                </div>""",
                unsafe_allow_html=True,
            )


def _render_app_table(result) -> None:
    """Sortable application table with TIME classification."""
    if not result.app_scores:
        return

    st.markdown("### Application Scores")

    import pandas as pd

    rows = []
    for s in result.app_scores:
        tc = s.time_class.value
        rows.append({
            "Application":      s.app_label,
            "TIME":             tc,
            "Portfolio Score":  s.portfolio_score,
            "Business Value":   round(s.business_value, 1),
            "Technical Fit":    round(s.technical_fit, 1),
            "Risk":             round(s.risk_score, 1),
            "Strategic Align":  round(s.strategic_align, 1),
            "Owner":            s.owner or "—",
            "Lifecycle":        s.lifecycle or "—",
            "Rationale":        s.rationale,
        })

    df = pd.DataFrame(rows).sort_values("Portfolio Score", ascending=False)

    # Filter controls
    filter_col, _ = st.columns([2, 5])
    with filter_col:
        tc_filter = st.multiselect(
            "Filter by TIME class",
            options=["Invest", "Tolerate", "Migrate", "Eliminate"],
            default=[],
            key="portfolio_tc_filter",
        )

    if tc_filter:
        df = df[df["TIME"].str.contains("|".join(tc_filter))]

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Portfolio Score": st.column_config.ProgressColumn(
                "Portfolio Score",
                min_value=0,
                max_value=10,
                format="%.1f",
            ),
        },
    )
    st.caption(f"{len(df)} of {len(rows)} applications shown")


def _render_rationalisations(result) -> None:
    """Show rationalisation action plan."""
    st.markdown("### Rationalisation Actions")
    for r in result.rationalisations:
        tc = r.time_class.value if hasattr(r.time_class, "value") else str(r.time_class)
        colour = _TIME_COLOUR.get(tc, GREY_TEXT)
        with st.expander(f"[{tc}] {r.app_label} — {r.action}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Timeline",   r.timeline)
            with col2:
                st.metric("Savings",    r.saving_band)
            with col3:
                st.metric("Exec. Risk", r.risk)
            if hasattr(r, "dependencies") and r.dependencies:
                st.markdown("**Dependencies to migrate:**")
                for dep in r.dependencies:
                    st.markdown(f"  - {dep}")
