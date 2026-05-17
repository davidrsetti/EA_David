"""ui/gap_roadmap_tab.py — Gap Analysis, AI Roadmap, and What-if Scenario tab."""
from __future__ import annotations

import json
import streamlit as st
import pandas as pd


def render(orange: str, grey_muted: str, grey_line: str, white: str, near_black: str) -> None:
    st.markdown("## 🔍 Gap Analysis & AI Roadmap")
    st.caption("Detect architectural gaps, generate AI roadmaps, and run what-if scenarios.")

    inner_tab_gap, inner_tab_road, inner_tab_scenario, inner_tab_validate = st.tabs(
        ["Gap Analysis", "AI Roadmap", "What-If Scenario", "KG Validation"]
    )

    # ── Gap Analysis ────────────────────────────────────────────────────
    with inner_tab_gap:
        st.markdown("### Architectural Gap Analysis")
        st.caption("Scan the knowledge graph for capability gaps, orphaned apps, governance issues, and more.")

        if st.button("Run Gap Analysis", key="gap_run", type="primary"):
            with st.spinner("Scanning knowledge graph for gaps…"):
                try:
                    from nexus.core.gap_analyzer import run_full_gap_analysis
                    result = run_full_gap_analysis()
                    st.session_state["gap_gr_result"] = result
                except Exception as exc:
                    st.error(f"Gap analysis failed: {exc}")

        result = st.session_state.get("gap_gr_result")
        if result:
            st.info(f"**{result.total_gaps} gaps detected** across {len(result.by_category)} categories")
            st.markdown(f"*{result.summary}*")

            col1, col2, col3, col4, col5 = st.columns(5)
            cats = result.by_category
            col1.metric("Capability Gaps",  cats.get("capability",  0))
            col2.metric("Orphaned Apps",    cats.get("orphan",      0))
            col3.metric("Governance Gaps",  cats.get("governance",  0))
            col4.metric("Data Gaps",        cats.get("data",        0))
            col5.metric("Integration Gaps", cats.get("integration", 0))

            if result.gaps:
                df = pd.DataFrame([vars(g) for g in result.gaps])

                def _color_severity(val):
                    return {
                        "High":   "background-color:#fee2e2;color:#991b1b",
                        "Medium": "background-color:#fef3c7;color:#92400e",
                        "Low":    "background-color:#dbeafe;color:#1e40af",
                    }.get(val, "")

                styled = df.style.applymap(_color_severity, subset=["severity"])
                st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── AI Roadmap ──────────────────────────────────────────────────────
    with inner_tab_road:
        st.markdown("### AI-Generated Architecture Roadmap")

        col_h, col_c = st.columns([1, 2])
        horizon    = col_h.selectbox("Horizon (months)", [6, 12, 18, 24, 36], index=2, key="road_horizon")
        constraints = col_c.text_input("Constraints (optional)", placeholder="e.g. budget cap £2M, no new vendors", key="road_constraints")

        if st.button("Generate Roadmap", key="road_generate", type="primary"):
            with st.spinner("Analysing gaps and generating roadmap via Claude…"):
                try:
                    from nexus.core.gap_analyzer     import run_full_gap_analysis
                    from nexus.core.roadmap_generator import generate_roadmap
                    gap  = run_full_gap_analysis()
                    road = generate_roadmap(gap, horizon_months=horizon, constraints=constraints)
                    st.session_state["gap_gr_roadmap"] = road
                except Exception as exc:
                    st.error(f"Roadmap generation failed: {exc}")

        road = st.session_state.get("gap_gr_roadmap")
        if road:
            st.markdown(f"**{road.total_initiatives} initiatives** over {road.horizon_months} months")
            st.markdown(f"_{road.executive_summary}_")

            for phase_num in sorted(road.phases.keys()):
                inits = road.phases[phase_num]
                with st.expander(f"Phase {phase_num}  ({len(inits)} initiatives)", expanded=phase_num == 1):
                    for init in inits:
                        priority_color = {"P1": orange, "P2": "#f59e0b", "P3": "#6b7280"}.get(init.priority, grey_muted)
                        st.markdown(
                            f'<div style="border-left:3px solid {priority_color};padding:.6rem 1rem;'
                            f'margin-bottom:.6rem;background:{white};border-radius:0 6px 6px 0">'
                            f'<span style="font-weight:700">{init.title}</span> '
                            f'<span style="font-size:.75rem;color:{grey_muted}">· {init.effort} · {init.priority}</span><br>'
                            f'<span style="font-size:.85rem">{init.description}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    # ── What-If Scenario ────────────────────────────────────────────────
    with inner_tab_scenario:
        st.markdown("### What-If Scenario Analysis")
        st.caption("Simulate the impact of decommissioning, merging, or replacing an entity.")

        col_e, col_a = st.columns(2)
        entity = col_e.text_input("Entity name (app, capability, or data asset)", key="scen_entity", placeholder="e.g. SAP ECC")
        action = col_a.selectbox("Action", ["decommission", "merge", "upgrade", "replace"], key="scen_action")
        replace_with = ""
        if action == "replace":
            replace_with = st.text_input("Replace with (name of new system)", key="scen_replace_with")

        if st.button("Run Scenario", key="scen_run", type="primary", disabled=not entity):
            with st.spinner(f"Simulating {action} of '{entity}'…"):
                try:
                    from nexus.core.scenario_engine import run_scenario
                    params = {"replace_with": replace_with} if replace_with else None
                    result = run_scenario(entity=entity, action=action, params=params)
                    st.session_state["gap_gr_scenario"] = result
                except Exception as exc:
                    st.error(f"Scenario failed: {exc}")

        scen = st.session_state.get("gap_gr_scenario")
        if scen:
            risk_color = "#dc2626" if scen.risk_score >= 70 else "#f59e0b" if scen.risk_score >= 40 else "#16a34a"
            st.markdown(
                f'<div style="padding:1rem;background:{white};border-radius:8px;border:1px solid {grey_line};margin-bottom:1rem">'
                f'<span style="font-size:1.1rem;font-weight:700">{scen.entity_label}</span> — '
                f'<span style="font-style:italic">{scen.action}</span><br>'
                f'<span style="color:{risk_color};font-size:1.3rem;font-weight:700">Risk Score: {scen.risk_score}/100</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("At-risk Apps",          len(scen.at_risk_apps))
            c2.metric("At-risk Capabilities",  len(scen.at_risk_capabilities))
            c3.metric("At-risk Data Products", len(scen.at_risk_data_products))

            st.markdown(f"**Analysis:** {scen.narrative}")

            if scen.recommendations:
                st.markdown("**Recommendations:**")
                for rec in scen.recommendations:
                    st.markdown(f"- {rec}")

    # ── KG Validation ───────────────────────────────────────────────────
    with inner_tab_validate:
        st.markdown("### Knowledge Graph Validation")
        st.caption("Run data quality, referential integrity, and governance completeness checks.")

        if st.button("Run Validation", key="val_run", type="primary"):
            with st.spinner("Validating knowledge graph…"):
                try:
                    from nexus.core.kg_validator import run_full_validation
                    report = run_full_validation()
                    st.session_state["gap_gr_valreport"] = report
                except Exception as exc:
                    st.error(f"Validation failed: {exc}")

        report = st.session_state.get("gap_gr_valreport")
        if report:
            passed_color = "#16a34a" if report.passed else "#dc2626"
            passed_label = "PASSED" if report.passed else "FAILED"
            st.markdown(
                f'<div style="padding:.8rem 1.2rem;background:{white};border:1px solid {grey_line};'
                f'border-left:4px solid {passed_color};border-radius:8px;margin-bottom:1rem">'
                f'<span style="color:{passed_color};font-weight:700;font-size:1rem">{passed_label}</span> — '
                f'{report.total_issues} issues found'
                f'</div>',
                unsafe_allow_html=True,
            )

            sev = report.by_severity
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Critical", sev.get("Critical", 0))
            c2.metric("High",     sev.get("High",     0))
            c3.metric("Medium",   sev.get("Medium",   0))
            c4.metric("Low",      sev.get("Low",      0))

            if report.shacl_summary:
                with st.expander("SHACL Report", expanded=False):
                    st.text(report.shacl_summary)

            if report.issues:
                df = pd.DataFrame([vars(i) for i in report.issues])

                def _sev_color(val):
                    return {
                        "Critical": "background-color:#fee2e2;color:#7f1d1d",
                        "High":     "background-color:#fed7aa;color:#7c2d12",
                        "Medium":   "background-color:#fef3c7;color:#78350f",
                        "Low":      "background-color:#dbeafe;color:#1e3a5f",
                    }.get(val, "")

                st.dataframe(
                    df.style.applymap(_sev_color, subset=["severity"]),
                    use_container_width=True,
                    hide_index=True,
                )
