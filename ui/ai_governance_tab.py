"""
ui/ai_governance_tab.py — AI Agent Governance Console (D-3)

Three-panel tab:
  1. Agent Registry — sortable table with risk-tier colour coding
  2. Data Access Map — agent_ecosystem diagram from artifact_creator
  3. Governance Findings — open AgentFindings grouped by severity, with resolve action

Plus: AI Governance Score strip (0–100) built from four signals.
"""
from __future__ import annotations

import streamlit as st

from nexus.ui.theme import (
    ORANGE, ORANGE_DARK, ORANGE_LIGHT, NEAR_BLACK, WHITE,
    GREY_TEXT, GREY_DARK, GREY_LINE, GREY_MUTED, SURFACE_2,
)
from nexus.ui.icons import icon, mat

_TIER_COLOURS = {
    "Critical": NEAR_BLACK,
    "High":     ORANGE_DARK,
    "Medium":   ORANGE,
    "Low":      GREY_TEXT,
    "":         GREY_MUTED,
}

_SEV_COLOURS = {
    "Critical": NEAR_BLACK,
    "High":     ORANGE_DARK,
    "Medium":   ORANGE,
    "Low":      GREY_TEXT,
}

_SCORE_SIGNALS = [
    ("tier_coverage",   "Risk Tier Coverage",      "% agents with a risk tier assigned"),
    ("owner_coverage",  "Owner Coverage",           "% agents with a designated owner"),
    ("finding_health",  "Finding Health",           "% agents with no open Critical/High findings"),
    ("data_governance", "Data Governance",          "% Restricted-data agents with a risk tier"),
]


def render_ai_governance_tab(connected: bool, user_role: str) -> None:
    st.markdown(
        f"""
        <div style="border-left:4px solid {ORANGE};padding-left:1rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:.8rem">
          <span>{icon("bot", size=26, color=ORANGE)}</span>
          <div>
            <h2 style="margin:0;font-size:1.4rem;color:{NEAR_BLACK}">AI Agent Governance Console</h2>
            <p style="margin:.25rem 0 0;color:{GREY_TEXT};font-size:.9rem">
              Complete picture of the AI agent estate: registry, data access scope,
              open responsible-AI findings, and a composite governance score — all
              derived from the live knowledge graph.
            </p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not connected:
        st.info("Connect to Stardog in the sidebar to load the AI agent registry.")
        _render_empty_score()
        return

    # ── Run / cache ───────────────────────────────────────────────────────────
    refresh = st.button(f"{mat('refresh')}  Refresh agent data", key="ai_gov_refresh")
    if refresh or "ai_gov_result" not in st.session_state:
        with st.spinner("Pulling AI agent registry from knowledge graph…"):
            try:
                from nexus.core.ai_governance import run_ai_governance
                result = run_ai_governance(user_role=user_role)
                st.session_state["ai_gov_result"] = result
            except Exception as exc:
                st.error(f"AI governance query failed: {exc}")
                return

    result = st.session_state.get("ai_gov_result")
    if result is None:
        return

    if result.error:
        st.error(result.error)

    # ── Governance Score strip ────────────────────────────────────────────────
    _render_score_strip(result)
    st.markdown("---")

    # ── Three panels ─────────────────────────────────────────────────────────
    panel_registry, panel_map, panel_findings = st.tabs([
        f"{mat('list_alt')}  Agent Registry",
        f"{mat('hub')}  Data Access Map",
        f"{mat('error')}  Governance Findings",
    ])

    with panel_registry:
        _render_agent_registry(result, user_role)

    with panel_map:
        _render_data_access_map(connected)

    with panel_findings:
        _render_findings(result, user_role)


# ── Score strip ───────────────────────────────────────────────────────────────

def _render_score_strip(result) -> None:
    score = result.governance_score
    score_colour = NEAR_BLACK if score >= 75 else ORANGE if score >= 50 else ORANGE_DARK
    score_label  = "Good" if score >= 75 else "Needs attention" if score >= 50 else "At risk"

    st.markdown(
        f"""
        <div style="background:{WHITE};border:1px solid {GREY_LINE};border-radius:12px;
                    border-left:6px solid {score_colour};padding:1rem 1.5rem;
                    display:flex;justify-content:space-between;align-items:center;
                    margin-bottom:1rem">
          <div>
            <div style="font-size:1.1rem;font-weight:700;color:{NEAR_BLACK}">
              AI Governance Score
            </div>
            <div style="font-size:.82rem;color:{GREY_TEXT};margin-top:.15rem">
              {result.total_agents} agents registered &nbsp;·&nbsp;
              {result.agents_with_tiers} with risk tiers &nbsp;·&nbsp;
              {result.agents_with_owners} with owners &nbsp;·&nbsp;
              {result.restricted_unrated} Restricted-data agents unrated &nbsp;·&nbsp;
              {result.open_critical} open Critical/High findings
            </div>
          </div>
          <div style="text-align:right">
            <div style="font-size:2rem;font-weight:700;color:{score_colour}">{score}</div>
            <div style="font-size:.7rem;color:{score_colour};text-transform:uppercase;font-weight:600">{score_label}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    bd   = result.score_breakdown
    for col, (key, label, tip) in zip(cols, _SCORE_SIGNALS):
        pts = bd.get(key, 0)
        c   = NEAR_BLACK if pts >= 20 else ORANGE if pts >= 12 else ORANGE_DARK
        col.markdown(
            f"""
            <div style="background:{SURFACE_2};border:1px solid {GREY_LINE};border-radius:8px;
                        padding:.75rem 1rem;text-align:center" title="{tip}">
              <div style="font-size:1.4rem;font-weight:700;color:{c}">{pts}<span style="font-size:.75rem;color:{GREY_MUTED}">/25</span></div>
              <div style="font-size:.72rem;color:{GREY_TEXT};margin-top:.2rem">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_empty_score() -> None:
    st.markdown(
        f"""
        <div style="background:{SURFACE_2};border:1px solid {GREY_LINE};border-radius:12px;
                    padding:2rem;text-align:center;color:{GREY_TEXT};margin-top:1rem">
          <div style="margin-bottom:.5rem;color:{GREY_MUTED}">{icon("bot", size=36, color=GREY_MUTED)}</div>
          <div style="font-weight:600;color:{NEAR_BLACK}">No data — connect to Stardog to compute the AI Governance Score</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Agent Registry ────────────────────────────────────────────────────────────

def _render_agent_registry(result, user_role: str) -> None:
    agents = result.agents
    if not agents:
        st.info("No AI agents found in the knowledge graph.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns(3)
    tiers     = sorted({a.risk_tier for a in agents if a.risk_tier})
    platforms = sorted({a.platform  for a in agents if a.platform})

    sel_tiers  = f1.multiselect("Risk tier", tiers,  key="ai_gov_tier_filter")
    sel_plats  = f2.multiselect("Platform",  platforms, key="ai_gov_plat_filter")
    only_risks = f3.checkbox("Only Restricted data agents", key="ai_gov_restricted_only")

    filtered = agents
    if sel_tiers:
        filtered = [a for a in filtered if a.risk_tier in sel_tiers]
    if sel_plats:
        filtered = [a for a in filtered if a.platform in sel_plats]
    if only_risks:
        filtered = [a for a in filtered if "Restricted" in a.classifications]

    st.caption(f"Showing {len(filtered)} of {len(agents)} agents")

    # ── Table ─────────────────────────────────────────────────────────────────
    for agent in filtered:
        tc = _TIER_COLOURS.get(agent.risk_tier, _TIER_COLOURS[""])
        # Solid black-or-orange chip with white text for high tiers; outlined chip for unrated.
        if agent.risk_tier in ("Critical", "High"):
            tier_badge = (
                f'<span style="background:{tc};color:{WHITE};border:1px solid {tc};'
                f'border-radius:4px;padding:.1rem .5rem;font-size:.72rem;font-weight:600">'
                f'{agent.risk_tier}</span>'
            )
        else:
            tier_badge = (
                f'<span style="background:{WHITE};color:{tc};border:1px solid {GREY_LINE};'
                f'border-radius:4px;padding:.1rem .5rem;font-size:.72rem;font-weight:600">'
                f'{agent.risk_tier or "Unrated"}</span>'
            )
        cls_badges = " ".join(
            f'<span style="background:{SURFACE_2};color:{NEAR_BLACK};border:1px solid {GREY_LINE};'
            f'border-radius:3px;padding:.05rem .35rem;font-size:.68rem">{c}</span>'
            for c in agent.classifications
        )
        finding_colour = ORANGE_DARK if agent.critical_findings else ORANGE if agent.open_findings else NEAR_BLACK
        finding_text   = (
            f'{mat("warning")} {agent.open_findings} open ({agent.critical_findings} Crit/High)'
            if agent.open_findings else f'{mat("check_circle")} No open findings'
        )

        with st.expander(f"{agent.label}  ·  {agent.platform or 'Unknown platform'}", expanded=False):
            left, right = st.columns([2, 1])
            with left:
                st.markdown(
                    f"{tier_badge} &nbsp; "
                    f'<span style="color:{GREY_TEXT};font-size:.8rem">Owner: <strong>{agent.owner or "Unassigned"}</strong></span>'
                    f'<br/><span style="font-size:.75rem;color:{finding_colour}">{finding_text}</span>',
                    unsafe_allow_html=True,
                )
                if agent.data_assets:
                    st.markdown(f"**Data assets ({len(agent.data_assets)}):** " + ", ".join(agent.data_assets[:6])
                                + (f" +{len(agent.data_assets)-6} more" if len(agent.data_assets) > 6 else ""))
                if cls_badges:
                    st.markdown("**Data classifications:** " + cls_badges, unsafe_allow_html=True)
            with right:
                if agent.tools:
                    st.markdown("**Tools:**")
                    for t in agent.tools[:8]:
                        st.markdown(f"- {t}")
                    if len(agent.tools) > 8:
                        st.caption(f"+{len(agent.tools)-8} more tools")

            if user_role in ("admin", "data-steward") and not agent.risk_tier:
                st.warning("This agent has no risk tier assigned — consider classifying it.", icon=":material/warning:")


# ── Data Access Map ───────────────────────────────────────────────────────────

def _render_data_access_map(connected: bool) -> None:
    st.markdown(
        "Agent ecosystem diagram generated from the live graph — shows all AI agents, "
        "the data assets they access, and their data classifications."
    )

    depth = st.slider("Graph depth", 1, 3, 2, key="ai_gov_map_depth")
    fmt   = st.radio("Format", ["dot", "mermaid"], horizontal=True, key="ai_gov_map_fmt")
    gen   = st.button(f"{mat('hub')}  Generate data access map", key="ai_gov_map_gen")

    if gen or "ai_gov_map_result" in st.session_state:
        if gen:
            with st.spinner("Generating agent ecosystem diagram…"):
                try:
                    from nexus.core.artifact_creator import generate_diagram
                    diagram = generate_diagram(
                        diagram_type="agent_ecosystem",
                        entity="",
                        depth=depth,
                        fmt=fmt,
                        domain_filter="",
                        max_nodes=60,
                    )
                    st.session_state["ai_gov_map_result"] = diagram
                except Exception as exc:
                    st.error(f"Diagram generation failed: {exc}")
                    return

        diagram = st.session_state.get("ai_gov_map_result")
        if diagram is None:
            return

        if diagram.error:
            st.warning(f"Diagram warning: {diagram.error}")

        if diagram.fmt == "dot" and diagram.content:
            st.graphviz_chart(diagram.content, use_container_width=True)
        elif diagram.fmt == "mermaid" and diagram.content:
            mermaid_html = f"""
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <div class="mermaid">{diagram.content}</div>
            <script>mermaid.initialize({{startOnLoad:true,theme:'neutral'}});</script>
            """
            st.components.v1.html(mermaid_html, height=600, scrolling=True)
        else:
            st.info("No diagram content returned — check that ai:Agent instances are loaded in the graph.")

        if diagram.node_count:
            st.caption(f"{diagram.node_count} nodes · {diagram.edge_count or 0} edges")


# ── Governance Findings ───────────────────────────────────────────────────────

def _render_findings(result, user_role: str) -> None:
    findings = result.findings
    if not findings:
        st.success("No open governance findings in the knowledge graph.")
        return

    # Severity groups
    groups: dict[str, list] = {"Critical": [], "High": [], "Medium": [], "Low": [], "Unknown": []}
    for f in findings:
        sev = f.severity or "Unknown"
        groups.setdefault(sev, []).append(f)

    for sev in ["Critical", "High", "Medium", "Low", "Unknown"]:
        bucket = groups.get(sev, [])
        if not bucket:
            continue
        colour = _SEV_COLOURS.get(sev, GREY_MUTED)
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:.5rem;margin:.75rem 0 .35rem">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{colour};display:inline-block"></span>'
            f'<strong style="color:{colour}">{sev}</strong>'
            f'<span style="color:{GREY_MUTED};font-size:.8rem">({len(bucket)})</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for finding in bucket:
            with st.expander(f"{finding.label}  —  {finding.agent_label or 'No agent linked'}", expanded=sev == "Critical"):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**Status:** {finding.status}")
                    if finding.asset_label:
                        st.markdown(f"**Affected asset:** {finding.asset_label}")
                    st.caption(f"URI: `{finding.finding_uri}`")
                with c2:
                    if user_role in ("admin", "data-steward"):
                        if st.button(f"{mat('check')}  Resolve", key=f"resolve_{finding.finding_uri}", type="secondary"):
                            _resolve_finding(finding.finding_uri)
                    else:
                        st.caption("Resolve requires admin or data-steward role")


def _resolve_finding(finding_uri: str) -> None:
    try:
        from nexus.agents.findings import assert_finding
        assert_finding(
            entity_uri=finding_uri,
            finding_type="StatusUpdate",
            severity="Info",
            description="Marked as Resolved via AI Governance Console",
            status="Resolved",
        )
        del st.session_state["ai_gov_result"]
        st.success("Finding marked Resolved — refreshing…")
        st.rerun()
    except Exception as exc:
        st.error(f"Could not resolve finding: {exc}")
