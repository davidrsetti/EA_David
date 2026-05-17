"""
ui/impact_tab.py — Graph-Native Change Impact Radar (D-1)

The flagship differentiator: given any application, capability, or data asset
and a proposed change type, computes the full blast radius across 6 dimensions
using live graph traversal. No competitor can replicate this because none have
the semantic capability layer + data classification + AI agent registry
all in the same queryable knowledge graph.
"""
from __future__ import annotations
import streamlit as st

from nexus.ui.theme import (
    ORANGE, ORANGE_DARK, ORANGE_LIGHT, NEAR_BLACK, WHITE,
    GREY_TEXT, GREY_DARK, GREY_LINE, GREY_MUTED, SURFACE_2,
)
from nexus.ui.icons import icon, mat


_CHANGE_TYPES = [
    "Decommission",
    "Re-platform",
    "Major version upgrade",
    "Owner change",
    "Data classification change",
    "Integration removal",
]

_RISK_COLOURS = {
    "Critical": NEAR_BLACK,
    "High":     ORANGE_DARK,
    "Medium":   ORANGE,
    "Low":      GREY_TEXT,
}

_RING_EXAMPLE = [
    (mat("warning"),    "Direct Dependents",              NEAR_BLACK),
    (mat("share"),      "Indirect Dependents (depth 2)",  ORANGE),
    (mat("crop_free"),  "Capability Gaps",                ORANGE_DARK),
    (mat("shield"),     "Data Assets at Risk",            NEAR_BLACK),
    (mat("smart_toy"),  "AI Agents Affected",             GREY_DARK),
    (mat("group"),      "People to Notify",               GREY_TEXT),
]


def render_impact_tab(connected: bool, user_role: str) -> None:
    """Render the Change Impact Radar tab."""
    st.markdown(
        f"""
        <div style="border-left:4px solid {ORANGE};padding-left:1rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:.8rem">
          <span>{icon("zap", size=26, color=ORANGE)}</span>
          <div>
            <h2 style="margin:0;font-size:1.4rem;color:{NEAR_BLACK}">Change Impact Radar</h2>
            <p style="margin:.25rem 0 0;color:{GREY_TEXT};font-size:.9rem">
              Full blast radius analysis: 6 parallel graph traversals compute the impact of any
              proposed change across dependents, capabilities, data assets, AI agents, and people.
            </p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not connected:
        st.info("Connect to Stardog in the sidebar to run impact analysis.")
        _render_legend()
        return

    # ── Controls ──────────────────────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3 = st.columns([3, 2, 1])
    with ctrl1:
        entity = st.text_input(
            "Application, capability, or data asset",
            placeholder="e.g. SAP ERP, Order-to-Cash, Customer Data Platform",
            key="impact_entity",
        )
    with ctrl2:
        change_type = st.selectbox(
            "Proposed change",
            options=_CHANGE_TYPES,
            key="impact_change_type",
        )
    with ctrl3:
        st.markdown("<br>", unsafe_allow_html=True)
        analyse_btn = st.button(
            f"{mat('search')}  Analyse Impact",
            key="impact_run",
            type="primary",
            disabled=not entity,
        )

    if analyse_btn or "impact_result" in st.session_state:
        if analyse_btn:
            if not entity:
                st.warning("Enter an application, capability, or data asset name.")
                return
            with st.spinner(f"Running 6 parallel graph traversals for '{entity}'…"):
                try:
                    from nexus.core.impact_analyzer import analyze_change_impact
                    result = analyze_change_impact(
                        entity=entity.strip(),
                        change_type=change_type,
                        user_role=user_role,
                    )
                    st.session_state["impact_result"] = result
                    st.session_state["impact_entity_label"] = entity.strip()
                except Exception as exc:
                    st.error(f"Impact analysis failed: {exc}")
                    return

        result = st.session_state.get("impact_result")
        if result is None:
            return

        _render_risk_banner(result)
        st.markdown("---")
        _render_impact_rings(result)
        st.markdown("---")
        _render_narrative(result)
        _render_mitigations(result)

    else:
        _render_legend()


def _render_risk_banner(result) -> None:
    """Headline risk level and total affected count."""
    rc = _RISK_COLOURS.get(result.risk_level, GREY_TEXT)
    st.markdown(
        f"""
        <div style="background:{WHITE};border:1px solid {GREY_LINE};border-radius:12px;
                    border-left:6px solid {rc};padding:1rem 1.5rem;
                    display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-size:1.1rem;font-weight:700;color:{NEAR_BLACK}">
              {result.change_type}: <em>{result.entity}</em>
            </div>
            <div style="font-size:.85rem;color:{GREY_TEXT};margin-top:.2rem">
              {result.total_affected} entities affected across {sum(1 for r in result.rings if r.count>0)} impact categories
            </div>
          </div>
          <div style="text-align:right">
            <div style="font-size:1.4rem;font-weight:700;color:{rc}">{result.risk_level}</div>
            <div style="font-size:.7rem;color:{GREY_TEXT};text-transform:uppercase">Risk Level</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_impact_rings(result) -> None:
    """Six impact ring cards, one per traversal dimension."""
    st.markdown("### Impact Rings")

    cols = st.columns(3)
    for i, ring in enumerate(result.rings):
        with cols[i % 3]:
            empty = ring.count == 0
            bg = SURFACE_2 if empty else WHITE
            border = GREY_LINE if empty else ring.colour
            count_colour = GREY_MUTED if empty else ring.colour
            entity_list = ""
            if ring.entities:
                items = ring.entities[:8]
                entity_list = "".join(
                    f"<div style='font-size:.78rem;color:{GREY_DARK};padding:.1rem 0;"
                    f"border-bottom:1px solid {SURFACE_2}'>{e}</div>"
                    for e in items
                )
                if ring.count > 8:
                    entity_list += (
                        f"<div style='font-size:.75rem;color:{GREY_MUTED};padding:.2rem 0'>"
                        f"+{ring.count - 8} more…</div>"
                    )

            empty_caption = (
                f"<em style='font-size:.78rem;color:{GREY_MUTED}'>No impact detected</em>"
                if empty else entity_list
            )
            st.markdown(
                f"""
                <div style="background:{bg};border:1px solid {border};border-radius:8px;
                            border-top:4px solid {border};padding:1rem;
                            margin-bottom:.75rem;min-height:140px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
                    <div style="font-size:.8rem;font-weight:600;color:{GREY_DARK}">{ring.icon} {ring.label}</div>
                    <div style="font-size:1.4rem;font-weight:700;color:{count_colour}">{ring.count}</div>
                  </div>
                  {empty_caption}
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_narrative(result) -> None:
    """LLM-synthesised impact narrative."""
    if not result.narrative:
        return
    st.markdown("### Impact Summary")
    st.markdown(
        f"""<div style="background:{WHITE};border:1px solid {GREY_LINE};border-left:4px solid {ORANGE};border-radius:8px;
                       padding:1rem 1.25rem;font-size:.9rem;line-height:1.6;color:{NEAR_BLACK}">
          {result.narrative}
        </div>""",
        unsafe_allow_html=True,
    )


def _render_mitigations(result) -> None:
    """Mitigation checklist."""
    if not result.mitigations:
        return
    st.markdown("### Mitigation Checklist")
    for i, step in enumerate(result.mitigations, 1):
        st.markdown(
            f"""<div style="background:{WHITE};border:1px solid {GREY_LINE};border-radius:6px;
                           padding:.6rem 1rem;margin-bottom:.4rem;
                           display:flex;align-items:flex-start;gap:.75rem;font-size:.875rem;color:{NEAR_BLACK}">
              <span style="color:{ORANGE};font-weight:700;min-width:1.5rem">{i}.</span>
              <span>{step}</span>
            </div>""",
            unsafe_allow_html=True,
        )


def _render_legend() -> None:
    """Show the 6 impact ring types when no analysis has been run."""
    st.markdown("### How it works")
    st.markdown(
        "Enter any application, capability, or data asset name above and choose a change type. "
        "NEXUS runs **6 parallel SPARQL traversals** across the live knowledge graph to compute "
        "the full blast radius:"
    )
    cols = st.columns(3)
    for i, (ring_icon, label, colour) in enumerate(_RING_EXAMPLE):
        with cols[i % 3]:
            st.markdown(
                f"""<div style="background:{WHITE};border:1px solid {GREY_LINE};border-radius:8px;
                               border-left:4px solid {colour};padding:.6rem 1rem;
                               margin-bottom:.5rem;font-size:.85rem;color:{NEAR_BLACK}">
                  <strong>{ring_icon} {label}</strong>
                </div>""",
                unsafe_allow_html=True,
            )
    st.markdown(
        "---\n"
        "**Why no competitor can replicate this:** LeanIX shows direct CMDB relationships. "
        "ServiceNow Impact shows CI dependencies. Neither has the semantic capability layer, "
        "data classification layer, and AI agent registry all in the same queryable graph."
    )
