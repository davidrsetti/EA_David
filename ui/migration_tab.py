"""
ui/migration_tab.py — PBI Report Migration Portfolio tab for NEXUS.

Implements the rationalisation workflow from the EA Playbook:
  Retire / NEXUS / SAC / BDC+Databricks disposition scoring and approval.

Sections:
  1. Portfolio dashboard (metrics + Plotly disposition chart)
  2. Report inventory table (sortable, filterable)
  3. Score a report (C1–C10 sliders → disposition recommendation)
  4. Approve disposition (Domain Lead sign-off)
  5. Ingest inventory (upload Tabular Editor JSON export)
"""
from __future__ import annotations

import json
import requests
import streamlit as st
import pandas as pd

_API = "http://localhost:8000"

DISP_COLOURS = {
    "Retire":         "#6B7280",
    "NEXUS":          "#F36633",
    "SAC":            "#0070AD",
    "BDC+Databricks": "#FF3621",
}

CRITERION_LABELS = {
    "c1":  "C1 — Business value (15%)",
    "c2":  "C2 — Usage telemetry (15%)",
    "c3":  "C3 — Overlap / duplication (10%)",
    "c4":  "C4 — Source pattern (10%)",
    "c5":  "C5 — Logic complexity (10%)",
    "c6":  "C6 — Data volume & latency (10%)",
    "c7":  "C7 — Interactivity pattern (10%)",
    "c8":  "C8 — Persona (10%)",
    "c10": "C10 — NEXUS strategic alignment (10%)",
}

CRITERION_HELP = {
    "c1":  "5 = Board/regulatory dependency. 0 = No owner.",
    "c2":  "5 = >50 weekly viewers. 0 = 0 opens in 90 days.",
    "c3":  "5 = Fully duplicated. 0 = Unique semantics.",
    "c4":  "5 = Single BEx on BW4. 0 = Hand-crafted M against flat extracts.",
    "c5":  "5 = 100+ DAX measures, complex M. 0 = <10 measures, simple star.",
    "c6":  "5 = >50M rows, sub-hour SLA. 0 = <1M rows, monthly.",
    "c7":  "5 = Conversational / ad-hoc. 0 = Pixel-perfect PDF.",
    "c8":  "5 = Board / Exec. 0 = Power user / analyst.",
    "c10": "5 = KPI/lineage/ownership questions dominate. 0 = Pure numeric exploration.",
}


def _api_get(path: str) -> dict:
    try:
        r = requests.get(f"{_API}{path}", timeout=10)
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def _api_post(path: str, body: dict) -> dict:
    try:
        r = requests.post(f"{_API}{path}", json=body, timeout=15)
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def render(ORANGE: str, GREY_MUTED: str, GREY_LINE: str, WHITE: str, NEAR_BLACK: str):
    """Render the Report Migration tab. Called from app.py."""

    st.markdown(
        f'<div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;'
        f'color:{ORANGE};text-transform:uppercase;margin-bottom:.8rem">'
        f'PBI → BDC / SAC / NEXUS Rationalisation</div>',
        unsafe_allow_html=True,
    )

    # ── Section 0: Ontology Setup ───────────────────────────────────────
    with st.expander("Graph Setup — Load SAP Migration Ontology", expanded=False):
        st.caption(
            "Load the `kpi:` + `mig:` + `bw:` ontology into Stardog as named graph "
            "`urn:SAP_Migration`. Required before any migration SPARQL will return results. "
            "Idempotent — safe to re-run after ontology updates."
        )
        if st.button("Load / Refresh Ontology into Stardog", use_container_width=True, key="mig_load_ont"):
            with st.spinner("Loading ontology…"):
                result = _api_post("/v1/migration/load-ontology", {})
                if "error" not in result and result.get("status") == "ok":
                    st.success(
                        f"Ontology loaded into `{result['graph']}` "
                        f"({result['bytes']:,} bytes)"
                    )
                else:
                    st.error(f"Load failed: {result}")

    # ── Section 1: Portfolio Dashboard ─────────────────────────────────
    st.subheader("Portfolio Dashboard", anchor=False)
    dash = _api_get("/v1/migration/dashboard")
    if "error" not in dash:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Reports", dash.get("total_reports", 0))
        c2.metric("Classified", dash.get("classified_count", 0))
        c3.metric("% Classified", f"{dash.get('pct_classified', 0):.1f}%")

        rows = dash.get("by_disposition", [])
        if rows:
            try:
                import plotly.graph_objects as go
                labels, values, colours = [], [], []
                disp_map = {
                    "https://ontology.ea.example.org/migration#Retire":            "Retire",
                    "https://ontology.ea.example.org/migration#ToNEXUS":           "NEXUS",
                    "https://ontology.ea.example.org/migration#ToSAC":             "SAC",
                    "https://ontology.ea.example.org/migration#ToBDCDatabricks":   "BDC+Databricks",
                }
                for row in rows:
                    d = row.get("disposition", "Unclassified")
                    label = disp_map.get(d, d.split("#")[-1] if d else "Unclassified")
                    labels.append(label)
                    values.append(int(row.get("count", 0)))
                    colours.append(DISP_COLOURS.get(label, GREY_MUTED))
                fig = go.Figure(go.Pie(
                    labels=labels, values=values,
                    marker_colors=colours,
                    hole=0.45, textinfo="label+percent",
                ))
                fig.update_layout(
                    margin=dict(l=0, r=0, t=10, b=0), height=280,
                    showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.info("Install plotly for the disposition chart.")
    else:
        st.caption(f"Dashboard unavailable: {dash['error']}")

    st.divider()

    # ── Section 2: Report Inventory ─────────────────────────────────────
    st.subheader("Report Inventory", anchor=False)
    disp_filter = st.selectbox(
        "Filter by disposition",
        ["All", "Retire", "NEXUS", "SAC", "BDC+Databricks"],
        key="mig_disp_filter",
    )
    inv_path = "/v1/migration/reports"
    if disp_filter != "All":
        inv_path += f"?disposition={disp_filter}"
    inv = _api_get(inv_path)
    if "error" not in inv and inv.get("reports"):
        df = pd.DataFrame(inv["reports"])
        rename_cols = {
            "label": "Report", "workspace": "Workspace",
            "proposed": "Proposed", "approved": "Approved",
            "score": "Score", "approvedBy": "Approved By",
        }
        df = df.rename(columns={k: v for k, v in rename_cols.items() if k in df.columns})
        # Shorten disposition URIs
        for col in ("Proposed", "Approved"):
            if col in df.columns:
                df[col] = df[col].str.split("#").str[-1].replace({
                    "Retire": "Retire", "ToNEXUS": "NEXUS",
                    "ToSAC": "SAC", "ToBDCDatabricks": "BDC+Databricks",
                })
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{inv.get('count', 0)} reports")
    elif "error" in inv:
        st.caption(f"Inventory unavailable: {inv['error']}")
    else:
        st.info("No reports ingested yet. Use the Ingest section below to load your PBI inventory.")

    st.divider()

    # ── Section 3: Score a Report ───────────────────────────────────────
    st.subheader("Score a Report", anchor=False)
    st.caption("Enter C1–C10 criterion scores (0–5) to get a disposition recommendation.")

    with st.form("score_form"):
        report_label = st.text_input("Report name (optional, for reference)")
        cols = st.columns(3)
        criterion_values: dict[str, float] = {}
        for i, (key, label) in enumerate(CRITERION_LABELS.items()):
            with cols[i % 3]:
                criterion_values[key] = st.slider(
                    label, min_value=0.0, max_value=5.0, value=2.5, step=0.5,
                    help=CRITERION_HELP.get(key, ""),
                    key=f"mig_score_{key}",
                )
        gxp = st.checkbox("C9 — GxP / regulated artefact (override → SAC/Veeva)", value=False)
        submitted = st.form_submit_button("Calculate Disposition", use_container_width=True)

    if submitted:
        payload = {**criterion_values, "c9": gxp, "label": report_label}
        result = _api_post("/v1/migration/score", payload)
        if "error" not in result:
            disp  = result.get("disposition", "?")
            score = result.get("weighted_score", 0)
            colour = DISP_COLOURS.get(disp, GREY_MUTED)
            st.markdown(
                f'<div style="background:{colour}18;border-left:4px solid {colour};'
                f'border-radius:8px;padding:.8rem 1.2rem;margin:.6rem 0">'
                f'<div style="font-size:.72rem;font-weight:700;letter-spacing:.08em;'
                f'color:{colour};text-transform:uppercase">Recommended Disposition</div>'
                f'<div style="font-size:1.4rem;font-weight:700;color:{colour}">{disp}</div>'
                f'<div style="font-size:.82rem;color:#555;margin-top:.3rem">'
                f'Weighted score: <b>{score:.2f}/5.0</b> · '
                f'Rule: <code>{result.get("triggered_rule","")}</code></div>'
                f'<div style="font-size:.8rem;color:#444;margin-top:.4rem">'
                f'{result.get("rationale","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.error(f"Scoring failed: {result['error']}")

    st.divider()

    # ── Section 4: Approve Disposition ─────────────────────────────────
    st.subheader("Approve Disposition", anchor=False)
    st.caption("Domain Lead sign-off — writes mig:approvedDisposition to the graph.")

    with st.form("approve_form"):
        report_id  = st.text_input("Report ID (URL-safe name, e.g. 'Workspace1_SalesReport')")
        disp_sel   = st.selectbox("Approved Disposition", ["Retire", "NEXUS", "SAC", "BDC+Databricks"])
        approver   = st.text_input("Your name / user ID")
        approved   = st.form_submit_button("Approve", use_container_width=True)

    if approved:
        if not report_id or not approver:
            st.warning("Report ID and approver name are required.")
        else:
            result = _api_post(
                f"/v1/migration/approve/{report_id}",
                {"disposition": disp_sel, "approver": approver},
            )
            if "error" not in result and "report_uri" in result:
                st.success(f"Approved: {disp_sel} for {result['report_uri']}")
            else:
                st.error(f"Approval failed: {result}")

    st.divider()

    # ── Section 5: Ingest Inventory ─────────────────────────────────────
    st.subheader("Ingest Report Inventory", anchor=False)
    st.caption(
        "Upload a JSON file exported from Tabular Editor (list of report objects). "
        "Each object must have `name` and `workspace`; optionally `info_provider`, "
        "`dax_measure_count`, `weekly_viewers`, `gxp`, `description`, and c1–c10 scores."
    )

    uploaded = st.file_uploader("Upload report inventory JSON", type=["json"], key="mig_upload")
    if uploaded:
        try:
            data = json.load(uploaded)
            if not isinstance(data, list):
                data = [data]
            st.write(f"Found {len(data)} reports. Preview (first 5):")
            st.json(data[:5])
            if st.button("Ingest into NEXUS graph", use_container_width=True):
                result = _api_post("/v1/migration/ingest", data)
                if "error" not in result:
                    st.success(f"Ingested {result.get('ingested', 0)} of {len(data)} reports.")
                    if result.get("results"):
                        failed = [r for r in result["results"] if not r["ok"]]
                        if failed:
                            st.warning(f"{len(failed)} failed:")
                            for f in failed[:5]:
                                st.caption(f"  {f['name']}: {f['uri']}")
                else:
                    st.error(f"Ingest failed: {result['error']}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")

    st.divider()

    # ── Section 6: Register Databricks Data Product ─────────────────────
    st.subheader("Register Databricks Data Product", anchor=False)
    st.caption(
        "Assert a Databricks table as a `kpi:DataProduct` node in the NEXUS graph so "
        "federated KPI queries can locate and query it. The sample table from `.env` is "
        "pre-filled — override for any table."
    )

    try:
        import requests as _req
        _cfg = _req.get(f"{_API}/v1/migration/config", timeout=3).json()
        _default_table = _cfg.get("sample_table", "")
    except Exception:
        _default_table = ""

    with st.form("register_dp_form"):
        dp_table = st.text_input(
            "Databricks table (catalog.schema.table)",
            value=_default_table,
            placeholder="rx_g_cda_devtest001.kpi_common.kpi_agg_customer_facing_days_and_flsl_coaching",
        )
        dp_label = st.text_input("Display label (optional, defaults to table name)")
        dp_desc  = st.text_area("Description (optional)", height=70)
        dp_kpi   = st.text_input(
            "Linked KPI name (optional)",
            placeholder="e.g. Customer Facing Days",
            help="Creates a kpi:KPI node and links this data product to it.",
        )
        register = st.form_submit_button("Register in NEXUS Graph", use_container_width=True)

    if register:
        if not dp_table.strip():
            st.warning("Table name is required.")
        else:
            result = _api_post(
                "/v1/migration/register-data-product",
                {"table": dp_table.strip(), "label": dp_label.strip(),
                 "description": dp_desc.strip(), "kpi_label": dp_kpi.strip()},
            )
            if "error" not in result and "data_product_uri" in result:
                st.success(
                    f"Registered **{result['label']}** as `kpi:DataProduct`  \n"
                    f"`{result['data_product_uri']}`"
                )
            else:
                st.error(f"Registration failed: {result}")

    st.divider()

    # ── Section 7: SHACL Validation ─────────────────────────────────────
    st.subheader("Graph Validation", anchor=False)
    st.caption(
        "Run SHACL-equivalent constraint checks on the `kpi:` and `mig:` graphs. "
        "Each shape reports violations so you can identify gaps before migration waves."
    )

    if st.button("Run Validation", use_container_width=True, key="mig_validate"):
        with st.spinner("Checking constraints…"):
            report = _api_get("/v1/migration/validate")

        if "error" in report:
            st.error(f"Validation failed: {report['error']}")
        else:
            passed = report.get("passed", False)
            colour = DISP_COLOURS["NEXUS"] if passed else "#EF4444"
            st.markdown(
                f'<div style="background:{colour}18;border-left:4px solid {colour};'
                f'border-radius:8px;padding:.7rem 1.1rem;margin:.5rem 0">'
                f'<span style="font-weight:700;color:{colour}">'
                f'{"PASSED" if passed else "FAILED"}</span>'
                f' &nbsp;·&nbsp; {report.get("summary","")}'
                f'</div>',
                unsafe_allow_html=True,
            )

            SEVER_COLOUR = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#6B7280"}
            for shape in report.get("shapes", []):
                ok       = shape.get("passed", False)
                sev      = shape.get("severity", "Low")
                sc       = DISP_COLOURS["NEXUS"] if ok else SEVER_COLOUR.get(sev, GREY_MUTED)
                icon     = "✓" if ok else "✗"
                vcount   = shape.get("violation_count", 0)
                err      = shape.get("error")

                with st.expander(
                    f"{icon}  [{shape['shape_id']}] {shape['label']}  "
                    f"({'PASS' if ok else f'{vcount} violation(s)' if not err else 'ERROR'})",
                    expanded=not ok,
                ):
                    if err:
                        st.error(f"Shape error: {err}")
                    elif not ok and shape.get("violations"):
                        viols = shape["violations"]
                        df_v = pd.DataFrame(viols)
                        df_v.columns = ["URI", "Label"]
                        st.dataframe(df_v, use_container_width=True, hide_index=True)
                        if vcount > len(viols):
                            st.caption(f"Showing first {len(viols)} of {vcount} violations.")
                    else:
                        st.success("No violations found.")
