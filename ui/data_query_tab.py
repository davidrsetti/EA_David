"""
ui/data_query_tab.py — "📊 Data Query" tab: Text2SQL via EKG + UC metadata.

Flow:
  1. Select Business Unit + Data Domain(s)  [from <urn:EKG_UC_Enrichment>]
  2. StarDog discovers all tables assigned to that scope
  3. UC metadata provides full schema (catalog.schema.table + columns)
  4. Ask a question → LLM selects the right table(s) and generates SQL
  5. Review/edit SQL → run on Databricks → results + NL answer

⚙️  Manage BU & Domains expander (bottom) for CRUD on governance metadata.
"""
from __future__ import annotations

from urllib.parse import quote

import pandas as pd
import streamlit as st

from nexus.ui.icons import mat

# ── Constants ────────────────────────────────────────────────────────────────
UC_NS            = "urn:databricks:uc:"
UC_ONT_NS        = "urn:databricks:uc:ontology#"
UC_GRAPH         = "urn:EKG_UC_David"
ENRICHMENT_GRAPH = "urn:EKG_UC_Enrichment"

_PREFIXES = (
    f"PREFIX uc:   <{UC_ONT_NS}>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    "PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>\n"
)

# ── IRI / literal helpers ─────────────────────────────────────────────────────

def _enc(*parts):
    return "/".join(quote(str(p), safe="") for p in parts)

def _tbl_iri(cat, sch, tbl):  return f"<{UC_NS}table/{_enc(cat, sch, tbl)}>"
def _bu_iri(name):             return f"<{UC_NS}bu/{_enc(name)}>"
def _dom_iri(name):            return f"<{UC_NS}domain/{_enc(name)}>"

def _lit(v):
    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'

# ── Session state ─────────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "dq_bu":          None,
        "dq_domains":     [],
        "dq_scoped_tbls": [],   # [{catalog, schema, table, columns}]
        "dq_question":    "",
        "dq_sql":         "",
        "dq_result_cols": [],
        "dq_result_rows": [],
        "dq_answer":      "",
        "dq_mgmt_kw":     "",
        "dq_mgmt_matches":[],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _clear_query():
    for k in ("dq_sql", "dq_result_cols", "dq_result_rows", "dq_answer", "dq_question"):
        st.session_state[k] = "" if isinstance(st.session_state[k], str) else []
    # Also clear the bound widget state so the text-area visibly empties on rerun.
    for widget_key in ("_dq_question", "_dq_sql_area"):
        if widget_key in st.session_state:
            del st.session_state[widget_key]

# ── StarDog reads ─────────────────────────────────────────────────────────────

def _labels(stardog, cls, graph):
    q = f"{_PREFIXES}\nSELECT ?l WHERE {{ GRAPH <{graph}> {{ ?x a uc:{cls} ; rdfs:label ?l }} }} ORDER BY ?l"
    try:
        _, rows = stardog.to_rows(stardog.query(q))
        return [r["l"] for r in rows]
    except Exception:
        return []

def _get_bus(sd):     return _labels(sd, "BusinessUnit", ENRICHMENT_GRAPH)
def _get_domains(sd): return _labels(sd, "DataDomain",   ENRICHMENT_GRAPH)


def _get_domains_for_bu(sd, bu: str) -> list[str]:
    """Return only the Data Domains that have ≥1 table also belonging to ``bu``."""
    if not bu:
        return _get_domains(sd)
    q = f"""{_PREFIXES}
SELECT DISTINCT ?l WHERE {{
  GRAPH <{ENRICHMENT_GRAPH}> {{
    ?t uc:belongsToBU     ?_bu  . ?_bu  rdfs:label {_lit(bu)} .
    ?t uc:belongsToDomain ?_dom . ?_dom rdfs:label ?l .
  }}
}} ORDER BY ?l"""
    try:
        _, rows = sd.to_rows(sd.query(q))
        return [r["l"] for r in rows]
    except Exception:
        return []


def _fetch_scoped_tables(stardog, bu: str | None, domains: list[str]) -> list[dict]:
    """
    Return [{catalog, schema, table, columns}] for every table assigned to
    the selected BU and/or Domain(s) in the enrichment graph.
    """
    if not bu and not domains:
        return []

    bu_block = ""
    if bu:
        bu_block = f"""
  GRAPH <{ENRICHMENT_GRAPH}> {{
    ?t uc:belongsToBU ?_bu . ?_bu rdfs:label {_lit(bu)} .
  }}"""

    dom_block = ""
    if domains:
        vals = ", ".join(_lit(d) for d in domains)
        dom_block = f"""
  GRAPH <{ENRICHMENT_GRAPH}> {{
    ?t uc:belongsToDomain ?_dom . ?_dom rdfs:label ?_dl .
    FILTER(?_dl IN ({vals}))
  }}"""

    # Get distinct tables in scope
    q_tables = f"""{_PREFIXES}
SELECT DISTINCT ?catLabel ?schLabel ?tblLabel ?tblComment WHERE {{
  GRAPH <{UC_GRAPH}> {{
    ?t a uc:Table ; rdfs:label ?tblLabel ; uc:inSchema ?s .
    ?s rdfs:label ?schLabel ; uc:inCatalog ?c .
    ?c rdfs:label ?catLabel .
    OPTIONAL {{ ?t rdfs:comment ?tblComment . }}
  }}
  {bu_block}
  {dom_block}
}} ORDER BY ?catLabel ?schLabel ?tblLabel LIMIT 20
"""
    try:
        _, tbl_rows = stardog.to_rows(stardog.query(q_tables))
    except Exception as exc:
        st.warning(f"Could not load scoped tables: {exc}")
        return []

    results = []
    for row in tbl_rows:
        cat, sch, tbl = row["catLabel"], row["schLabel"], row["tblLabel"]
        cols = _fetch_columns(stardog, cat, sch, tbl)
        results.append({
            "catalog": cat, "schema": sch, "table": tbl,
            "description": row.get("tblComment", ""),
            "columns": cols,
        })
    return results


def _fetch_columns(stardog, cat, sch, tbl) -> list[dict]:
    q = f"""{_PREFIXES}
SELECT ?colName ?dataType ?ordinalPosition ?isNullable ?colComment WHERE {{
  GRAPH <{UC_GRAPH}> {{
    ?t a uc:Table ; rdfs:label {_lit(tbl)} ; uc:inSchema ?s .
    ?s rdfs:label {_lit(sch)} ; uc:inCatalog ?c .
    ?c rdfs:label {_lit(cat)} .
    ?t uc:hasColumn ?col .
    ?col rdfs:label ?colName ; uc:dataType ?dataType ;
         uc:ordinalPosition ?ordinalPosition ; uc:isNullable ?isNullable .
    OPTIONAL {{ ?col rdfs:comment ?colComment . }}
  }}
}} ORDER BY xsd:integer(?ordinalPosition)
"""
    try:
        _, rows = stardog.to_rows(stardog.query(q))
        return rows
    except Exception:
        return []

# ── Enrichment search (for management panel) ──────────────────────────────────

def _search_tables_unscoped(stardog, keyword: str) -> list[dict]:
    kw = keyword.lower().strip()
    if not kw:
        return []
    q = f"""{_PREFIXES}
SELECT ?catLabel ?schLabel ?tblLabel WHERE {{
  GRAPH <{UC_GRAPH}> {{
    ?t a uc:Table ; rdfs:label ?tblLabel ; uc:inSchema ?s .
    ?s rdfs:label ?schLabel ; uc:inCatalog ?c .
    ?c rdfs:label ?catLabel .
    FILTER(CONTAINS(LCASE(?tblLabel), "{kw}") || CONTAINS(LCASE(?schLabel), "{kw}"))
  }}
}} ORDER BY ?catLabel ?schLabel ?tblLabel LIMIT 30
"""
    try:
        _, rows = stardog.to_rows(stardog.query(q))
        return rows
    except Exception as exc:
        st.warning(f"Search failed: {exc}")
        return []

# ── Enrichment writes ─────────────────────────────────────────────────────────

def _create_bu(sd, name):
    sd.update(f"{_PREFIXES}\nINSERT DATA {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {_bu_iri(name)} a uc:BusinessUnit ; rdfs:label {_lit(name)} . }} }}")

def _delete_bu(sd, name):
    iri = _bu_iri(name)
    sd.update(f"""{_PREFIXES}
DELETE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {iri} ?p ?o . ?t uc:belongsToBU {iri} . }} }}
WHERE  {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {iri} a uc:BusinessUnit . OPTIONAL {{ {iri} ?p ?o }} OPTIONAL {{ ?t uc:belongsToBU {iri} }} }} }}""")

def _create_domain(sd, name):
    sd.update(f"{_PREFIXES}\nINSERT DATA {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {_dom_iri(name)} a uc:DataDomain ; rdfs:label {_lit(name)} . }} }}")

def _delete_domain(sd, name):
    iri = _dom_iri(name)
    sd.update(f"""{_PREFIXES}
DELETE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {iri} ?p ?o . ?t uc:belongsToDomain {iri} . }} }}
WHERE  {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {iri} a uc:DataDomain . OPTIONAL {{ {iri} ?p ?o }} OPTIONAL {{ ?t uc:belongsToDomain {iri} }} }} }}""")

def _assign_table_bu(sd, cat, sch, tbl, bu_name):
    ti = _tbl_iri(cat, sch, tbl)
    sd.update(f"{_PREFIXES}\nDELETE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {ti} uc:belongsToBU ?x }} }} WHERE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {ti} uc:belongsToBU ?x }} }}")
    if bu_name:
        sd.update(f"{_PREFIXES}\nINSERT DATA {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {ti} uc:belongsToBU {_bu_iri(bu_name)} . }} }}")

def _assign_table_domains(sd, cat, sch, tbl, domain_names):
    ti = _tbl_iri(cat, sch, tbl)
    sd.update(f"{_PREFIXES}\nDELETE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {ti} uc:belongsToDomain ?x }} }} WHERE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {ti} uc:belongsToDomain ?x }} }}")
    if domain_names:
        triples = " ".join(f"{ti} uc:belongsToDomain {_dom_iri(d)} ." for d in domain_names)
        sd.update(f"{_PREFIXES}\nINSERT DATA {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {triples} }} }}")

def _get_table_bu(sd, cat, sch, tbl):
    q = f"{_PREFIXES}\nSELECT ?l WHERE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {_tbl_iri(cat,sch,tbl)} uc:belongsToBU ?b . ?b rdfs:label ?l }} }} LIMIT 1"
    try:
        _, rows = sd.to_rows(sd.query(q))
        return rows[0]["l"] if rows else None
    except Exception:
        return None

def _get_table_domains(sd, cat, sch, tbl):
    q = f"{_PREFIXES}\nSELECT ?l WHERE {{ GRAPH <{ENRICHMENT_GRAPH}> {{ {_tbl_iri(cat,sch,tbl)} uc:belongsToDomain ?d . ?d rdfs:label ?l }} }} ORDER BY ?l"
    try:
        _, rows = sd.to_rows(sd.query(q))
        return [r["l"] for r in rows]
    except Exception:
        return []

# ── Management panel ──────────────────────────────────────────────────────────

def _render_manage_panel(stardog):
    with st.expander(f"{mat('settings')}  Manage Business Units & Data Domains", expanded=False):
        t_bu, t_dom, t_assign = st.tabs(["Business Units", "Data Domains", "Assign Tables"])

        with t_bu:
            for i, bu in enumerate(_get_bus(stardog)):
                c1, c2 = st.columns([9, 1])
                c1.write(bu)
                if c2.button(mat("delete"), key=f"_dbu_{i}"):
                    try: _delete_bu(stardog, bu); st.rerun()
                    except Exception as e: st.error(str(e))
            new = st.text_input("New Business Unit", key="_new_bu")
            if st.button(f"{mat('add')}  Add BU", key="_add_bu") and new.strip():
                try: _create_bu(stardog, new.strip()); st.rerun()
                except Exception as e: st.error(str(e))

        with t_dom:
            for i, dom in enumerate(_get_domains(stardog)):
                c1, c2 = st.columns([9, 1])
                c1.write(dom)
                if c2.button(mat("delete"), key=f"_ddom_{i}"):
                    try: _delete_domain(stardog, dom); st.rerun()
                    except Exception as e: st.error(str(e))
            new = st.text_input("New Data Domain", key="_new_dom")
            if st.button(f"{mat('add')}  Add Domain", key="_add_dom") and new.strip():
                try: _create_domain(stardog, new.strip()); st.rerun()
                except Exception as e: st.error(str(e))

        with t_assign:
            st.caption("Search for a table then assign it to a BU and/or Domains.")
            kw = st.text_input("Search tables", key="_assign_kw", placeholder="e.g. inventory")
            if kw != st.session_state.dq_mgmt_kw:
                st.session_state.dq_mgmt_kw = kw
                st.session_state.dq_mgmt_matches = _search_tables_unscoped(stardog, kw)

            matches = st.session_state.dq_mgmt_matches
            if matches:
                opts = [f"{r['catLabel']} › {r['schLabel']} › {r['tblLabel']}" for r in matches]
                sel = st.radio("Table", opts, key="_assign_radio")
                if sel:
                    mcat, msch, mtbl = sel.split(" › ")
                    bus_all  = ["(none)"] + _get_buses_all(stardog)
                    doms_all = _get_domains(stardog)
                    cur_bu   = _get_table_bu(stardog, mcat, msch, mtbl)
                    cur_doms = _get_table_domains(stardog, mcat, msch, mtbl)

                    s_bu = st.selectbox("BU", bus_all,
                                        index=bus_all.index(cur_bu) if cur_bu in bus_all else 0,
                                        key="_assign_bu")
                    s_doms = st.multiselect("Domains", doms_all,
                                            default=[d for d in cur_doms if d in doms_all],
                                            key="_assign_doms")
                    if st.button(f"{mat('save')}  Save", key="_assign_save"):
                        try:
                            _assign_table_bu(stardog, mcat, msch, mtbl,
                                             s_bu if s_bu != "(none)" else None)
                            _assign_table_domains(stardog, mcat, msch, mtbl, s_doms)
                            st.success(f"Saved: {mtbl} → BU={s_bu}, Domains={s_doms}")
                        except Exception as e:
                            st.error(str(e))
            elif kw:
                st.info("No tables found.")

def _get_buses_all(sd):  # alias to avoid shadowing
    return _get_bus(sd)  # already defined above

# ── Main render ───────────────────────────────────────────────────────────────

def render_data_query_tab(stardog, databricks):
    _init_state()

    st.markdown(f"### {mat('database')}  Data Query")

    if stardog is None or databricks is None:
        st.warning("Connect to StarDog using the sidebar to enable Data Query.")
        return

    # ── Scope selectors ───────────────────────────────────────────────────────
    all_bus  = _get_bus(stardog)
    all_doms_unfiltered = _get_domains(stardog)

    if not all_bus and not all_doms_unfiltered:
        st.info("No Business Units or Data Domains defined yet. Use the **Manage** panel below to create them, then assign tables.")
        _render_manage_panel(stardog)
        return

    col_bu, col_dom, col_clear = st.columns([3, 5, 1])

    with col_bu:
        bu_opts = ["— Select BU —"] + all_bus
        bu_sel = st.selectbox("Business Unit", bu_opts,
                              index=bu_opts.index(st.session_state.dq_bu)
                                    if st.session_state.dq_bu in bu_opts else 0,
                              key="_dq_bu", label_visibility="collapsed")
        new_bu = None if bu_sel == "— Select BU —" else bu_sel

    # Cascade: when a BU is chosen, only show Data Domains that have a table in that BU.
    domain_opts = _get_domains_for_bu(stardog, new_bu) if new_bu else all_doms_unfiltered

    with col_dom:
        dom_sel = st.multiselect("Data Domains", domain_opts,
                                 default=[d for d in st.session_state.dq_domains if d in domain_opts],
                                 key="_dq_doms", placeholder="Select Data Domain(s)…",
                                 label_visibility="collapsed")

    with col_clear:
        if st.button(mat("delete"), help="Clear question, SQL and results", use_container_width=True):
            _clear_query()
            st.rerun()

    # Reload scoped tables when BU/Domain changes
    if new_bu != st.session_state.dq_bu or dom_sel != st.session_state.dq_domains:
        st.session_state.dq_bu      = new_bu
        st.session_state.dq_domains = dom_sel
        _clear_query()
        if new_bu or dom_sel:
            with st.spinner("Loading tables from EKG…"):
                st.session_state.dq_scoped_tbls = _fetch_scoped_tables(stardog, new_bu, dom_sel)
        else:
            st.session_state.dq_scoped_tbls = []

    scoped = st.session_state.dq_scoped_tbls
    scope_ready = bool(new_bu or dom_sel)

    # Scope summary
    if scope_ready:
        if scoped:
            st.caption(f"{mat('folder_open')}  {len(scoped)} data product(s) in scope")
            with st.expander("Views and Tables", expanded=False):
                for t in scoped:
                    st.markdown(
                        f"**`{t['catalog']}`.`{t['schema']}`.`{t['table']}`**"
                        f"  ·  *data product / data set*"
                    )
                    if t.get("description"):
                        st.caption(t["description"])
        else:
            st.warning("No data products are assigned to this BU/Domain yet. Use the **Manage** panel below to assign tables.")

    st.markdown("---")

    # ── Question + Generate ───────────────────────────────────────────────────
    question_disabled = not (scope_ready and scoped)

    question = st.text_area(
        "Ask a question about your data",
        value=st.session_state.dq_question,
        placeholder="e.g. List the count of subscriptions for each resource type" if not question_disabled
                    else "Select a Business Unit and/or Data Domain with assigned tables to enable this",
        height=90,
        disabled=question_disabled,
        key="_dq_question",
    )
    st.session_state.dq_question = question

    btn_col, _, _ = st.columns([2, 4, 4])
    with btn_col:
        gen = st.button(f"{mat('auto_awesome')}  Generate SQL",
                        disabled=question_disabled or not question.strip(),
                        use_container_width=True)

    if gen and question.strip():
        with st.spinner("Analysing schema and generating SQL…"):
            try:
                from nexus.core.nl_to_sql import nl_to_sql
                sql = nl_to_sql(
                    question=question,
                    tables=scoped,
                    bu_context=new_bu or "",
                    domain_context=dom_sel or [],
                )
                st.session_state.dq_sql         = sql
                st.session_state.dq_result_cols = []
                st.session_state.dq_result_rows = []
                st.session_state.dq_answer      = ""
            except Exception as exc:
                st.error(f"SQL generation failed: {exc}")

    # ── Editable SQL + Run ────────────────────────────────────────────────────
    if st.session_state.dq_sql:
        edited_sql = st.text_area("Generated SQL (editable)",
                                  value=st.session_state.dq_sql,
                                  height=160, key="_dq_sql_area")

        run_col, _ = st.columns([2, 8])
        with run_col:
            run = st.button(f"{mat('play_arrow')}  Run", use_container_width=True)

        if run:
            with st.spinner("Running on Databricks…"):
                try:
                    cols_out, rows_out = databricks.query(edited_sql)
                    st.session_state.dq_result_cols = cols_out
                    st.session_state.dq_result_rows = rows_out
                    st.session_state.dq_answer      = ""
                except Exception as exc:
                    st.error(f"Query failed: {exc}")

    # ── Results ───────────────────────────────────────────────────────────────
    result_rows = st.session_state.dq_result_rows
    result_cols = st.session_state.dq_result_cols
    if result_rows:
        st.markdown("---")
        st.caption(f"{len(result_rows):,} rows returned")
        st.dataframe(pd.DataFrame(result_rows, columns=result_cols), use_container_width=True)

        if st.button(f"{mat('forum')}  Explain results", key="_dq_explain"):
            with st.spinner("Synthesising…"):
                try:
                    from nexus.core.answer_engine import synthesise
                    st.session_state.dq_answer = synthesise(
                        question=st.session_state.dq_question,
                        columns=result_cols,
                        rows=result_rows[:50],
                        sparql=st.session_state.dq_sql,
                        total_count=len(result_rows),
                    )
                except Exception as exc:
                    st.error(str(exc))

        if st.session_state.dq_answer:
            st.markdown(st.session_state.dq_answer)

    elif st.session_state.dq_sql and result_rows is not None and len(result_rows) == 0:
        st.info("Query returned 0 rows.")

    # ── Management panel ──────────────────────────────────────────────────────
    st.markdown("---")
    _render_manage_panel(stardog)
