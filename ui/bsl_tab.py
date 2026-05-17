"""ui/bsl_tab.py — Business Semantic Layer tab: KPI evaluation and business rule checking."""
from __future__ import annotations

import pandas as pd
import streamlit as st

_DOMAINS = ["All", "Finance", "HR", "Supply Chain", "Operations", "Sales", "Technology"]

_SEV_COLORS = {
    "Critical": "#EF4444",
    "High":     "#F97316",
    "Medium":   "#EAB308",
    "Low":      "#3B82F6",
}


def _init_state() -> None:
    defaults: dict = {
        "bsl_domain":           "All",
        "bsl_kpis":             None,
        "bsl_rules":            None,
        "bsl_kpi_value":        None,
        "bsl_all_kpi_values":   None,
        "bsl_violations":       None,
        "bsl_selected_kpi_uri": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _sev_row_style(severity: str) -> str:
    color = _SEV_COLORS.get(severity, "#6B7280")
    return f"background-color:{color}22;border-left:3px solid {color}"


def _color_severity(val: str) -> str:
    color = _SEV_COLORS.get(val, "")
    return f"color:{color};font-weight:600" if color else ""


def render(connected: bool = True) -> None:
    _init_state()

    st.markdown("### :material/bar_chart:  Business Semantic Layer")

    try:
        from nexus.core.bsl_engine import (
            list_kpis, evaluate_kpi, list_rules,
            check_rules, evaluate_all_kpis,
        )
    except ImportError as exc:
        st.error(f"BSL engine not configured: {exc}")
        return

    domain_sel = st.selectbox(
        "Domain",
        _DOMAINS,
        index=_DOMAINS.index(st.session_state.bsl_domain)
              if st.session_state.bsl_domain in _DOMAINS else 0,
        key="_bsl_domain_sel",
        label_visibility="collapsed",
    )
    st.session_state.bsl_domain = domain_sel
    domain_filter = "" if domain_sel == "All" else domain_sel

    tab_kpi, tab_rules = st.tabs([
        ":material/speed:  KPIs",
        ":material/rule:  Business Rules",
    ])

    # ── KPI tab ──────────────────────────────────────────────────────────────
    with tab_kpi:
        if st.session_state.bsl_kpis is None or st.session_state.get("_bsl_domain_last") != domain_sel:
            with st.spinner("Loading KPI definitions…"):
                try:
                    st.session_state.bsl_kpis = list_kpis(domain=domain_filter)
                    st.session_state["_bsl_domain_last"] = domain_sel
                    st.session_state.bsl_kpi_value      = None
                    st.session_state.bsl_all_kpi_values = None
                except Exception as exc:
                    st.error(f"Could not load KPIs: {exc}")
                    st.session_state.bsl_kpis = []

        kpis = st.session_state.bsl_kpis or []

        if not kpis:
            st.info("No KPI definitions found in the knowledge graph for this domain.")
        else:
            df_kpi = pd.DataFrame([
                {
                    "Label":   k.label or k.uri,
                    "Domain":  k.domain,
                    "Formula": k.formula,
                    "Unit":    k.unit,
                    "Owner":   k.owner,
                }
                for k in kpis
            ])
            st.dataframe(df_kpi, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Single KPI evaluation
        st.markdown("**Evaluate a KPI**")
        if kpis:
            kpi_options = {(k.label or k.uri): k.uri for k in kpis}
            selected_label = st.selectbox(
                "KPI",
                list(kpi_options.keys()),
                key="_bsl_kpi_sel",
                label_visibility="collapsed",
            )
            selected_uri = kpi_options.get(selected_label, "")

            col_eval, _ = st.columns([1, 4])
            with col_eval:
                if st.button(":material/play_arrow:  Evaluate", use_container_width=True, key="_bsl_eval_one"):
                    with st.spinner(f"Evaluating {selected_label}…"):
                        try:
                            st.session_state.bsl_kpi_value = evaluate_kpi(selected_uri)
                        except Exception as exc:
                            st.error(f"Evaluation failed: {exc}")
                            st.session_state.bsl_kpi_value = None

            kv = st.session_state.bsl_kpi_value
            if kv is not None:
                if kv.error:
                    st.error(f"{kv.label}: {kv.error}")
                else:
                    st.metric(
                        label=kv.label,
                        value=f"{kv.value} {kv.unit}".strip() if kv.value is not None else "—",
                    )
                    st.caption(f"Evaluated at {kv.evaluated_at}")

        st.markdown("---")

        # Evaluate all
        col_all, _ = st.columns([1, 4])
        with col_all:
            if st.button(":material/playlist_play:  Evaluate All KPIs", use_container_width=True, key="_bsl_eval_all"):
                if not kpis:
                    st.warning("No KPIs to evaluate.")
                else:
                    with st.spinner("Evaluating all KPIs…"):
                        try:
                            st.session_state.bsl_all_kpi_values = evaluate_all_kpis(domain=domain_filter)
                        except Exception as exc:
                            st.error(f"Batch evaluation failed: {exc}")
                            st.session_state.bsl_all_kpi_values = None

        all_vals = st.session_state.bsl_all_kpi_values
        if all_vals:
            rows_out = []
            for kv in all_vals:
                rows_out.append({
                    "KPI":          kv.label,
                    "Value":        kv.value if not kv.error else "—",
                    "Unit":         kv.unit,
                    "Evaluated At": kv.evaluated_at[:19].replace("T", " "),
                    "Error":        kv.error,
                })
            df_vals = pd.DataFrame(rows_out)
            st.dataframe(df_vals, use_container_width=True, hide_index=True)

    # ── Business Rules tab ───────────────────────────────────────────────────
    with tab_rules:
        if st.session_state.bsl_rules is None or st.session_state.get("_bsl_rules_domain_last") != domain_sel:
            with st.spinner("Loading business rules…"):
                try:
                    st.session_state.bsl_rules = list_rules(domain=domain_filter)
                    st.session_state["_bsl_rules_domain_last"] = domain_sel
                    st.session_state.bsl_violations = None
                except Exception as exc:
                    st.error(f"Could not load rules: {exc}")
                    st.session_state.bsl_rules = []

        rules = st.session_state.bsl_rules or []

        if not rules:
            st.info("No business rule definitions found in the knowledge graph for this domain.")
        else:
            df_rules = pd.DataFrame([
                {
                    "Label":    r.label or r.uri,
                    "Domain":   r.domain,
                    "Severity": r.severity,
                    "Rule":     r.rule_text,
                }
                for r in rules
            ])
            styled = df_rules.style.applymap(_color_severity, subset=["Severity"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("---")

        col_check, _ = st.columns([1, 4])
        with col_check:
            if st.button(":material/rule_settings:  Run Rule Check", use_container_width=True, key="_bsl_run_rules"):
                with st.spinner("Running rule checks…"):
                    try:
                        st.session_state.bsl_violations = check_rules(domain=domain_filter)
                    except Exception as exc:
                        st.error(f"Rule check failed: {exc}")
                        st.session_state.bsl_violations = None

        violations = st.session_state.bsl_violations
        if violations is not None:
            if not violations:
                st.success("No rule violations detected.")
            else:
                st.warning(f"{len(violations)} violation(s) found.")
                vdf = pd.DataFrame([
                    {
                        "Rule":         v.rule_label,
                        "Severity":     v.severity,
                        "Entity":       v.entity_label or v.entity_uri,
                        "Detail":       v.detail,
                    }
                    for v in violations
                ])
                styled_v = vdf.style.applymap(_color_severity, subset=["Severity"])
                st.dataframe(styled_v, use_container_width=True, hide_index=True)
