"""
ui/app.py - NEXUS Enterprise Conversational AI
Full pipeline: guard -> clarify -> confirm -> query -> answer + reasoning
+ SA Advisor tab with ArchiMate diagram generation
"""
import os, time, json, logging, sys
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
logging.basicConfig(level=logging.WARNING)

st.set_page_config(page_title="NEXUS", page_icon="◆", layout="wide", initial_sidebar_state="expanded")

from nexus.ui.theme import (
    inject_css, ORANGE, ORANGE_DARK, ORANGE_LIGHT, WHITE, NEAR_BLACK,
    GREY_TEXT, GREY_MUTED, GREY_LINE, GREY_DARK, SURFACE_2,
)
from nexus.ui.icons import icon, mat, TAB_LABELS

inject_css()

# SA Advisor card-specific styles (depth/intensity of the orange accent
# encodes ArchiMate layer; the chrome stays in the strict palette).
st.markdown(f"""
<style>
.sa-input-box,.sa-advisory-section{{background:{WHITE}!important;border:1px solid {GREY_LINE}!important;border-radius:10px!important;padding:1rem 1.2rem!important;margin-bottom:1rem!important;}}
.sa-section-label{{font-size:.72rem!important;font-weight:700!important;letter-spacing:.1em!important;color:{ORANGE}!important;text-transform:uppercase!important;margin-bottom:.5rem!important;}}
.sa-detail-card{{background:{WHITE}!important;border:1px solid {GREY_LINE}!important;border-left:3px solid {ORANGE}!important;border-radius:8px!important;padding:.8rem 1rem!important;margin-bottom:.6rem!important;}}
.sa-layer-band-Motivation{{border-left:4px solid {NEAR_BLACK}!important;}}
.sa-layer-band-Business{{border-left:4px solid {ORANGE_DARK}!important;}}
.sa-layer-band-Application{{border-left:4px solid {ORANGE}!important;}}
.sa-layer-band-Technology{{border-left:4px solid {GREY_DARK}!important;}}
::-webkit-scrollbar{{width:4px;height:4px;}}
::-webkit-scrollbar-track{{background:{SURFACE_2};}}
::-webkit-scrollbar-thumb{{background:{GREY_LINE};border-radius:2px;}}
::-webkit-scrollbar-thumb:hover{{background:{ORANGE};}}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────
for k, v in {
    "messages": [], "connected": False, "session_id": "",
    "pending_plan": None, "pending_question": "", "pending_clarification": "",
    "turn_count": 0,
    "sa_result": None, "sa_loading": False, "sa_prompt": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def make_client(endpoint, token, oai_key, db):
    """Set credentials, reset the StardogClient singleton, return a fresh client."""
    os.environ.update({
        "STARDOG_ENDPOINT": endpoint,
        "STARDOG_TOKEN":    token,
        "OPENAI_API_KEY":   oai_key,
        "STARDOG_DB":       db,
    })
    # Reset the module-level singleton so it picks up the new env vars
    import nexus.core.stardog_client as _sc
    _sc._client = None
    # Reset the frozen Settings singleton so it re-reads env vars
    import nexus.config.settings as _cfg
    _cfg.settings = _cfg.Settings()
    # Invalidate schema cache so the new endpoint's ontology is fetched fresh
    from nexus.core.sa_advisor_v2 import invalidate_schema_cache
    invalidate_schema_cache()
    from nexus.core.stardog_client import StardogClient
    client = StardogClient()
    _sc._client = client
    return client


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div style="text-align:center;padding:.5rem 0 1rem">'
        f'<div style="width:42px;height:42px;background:{NEAR_BLACK};border-radius:10px;'
        f'display:flex;align-items:center;justify-content:center;margin:0 auto .6rem;color:{ORANGE}">'
        f'{icon("network", size=22, color=ORANGE)}'
        f'</div>'
        f'<div style="color:{NEAR_BLACK};font-weight:700;font-size:1rem;margin-top:.2rem;letter-spacing:.04em">NEXUS</div>'
        f'<div style="color:{GREY_MUTED};font-size:.7rem">Knowledge Graph Platform</div></div>',
        unsafe_allow_html=True
    )

    with st.expander("Stardog Connection", expanded=not st.session_state.connected):
        endpoint  = st.text_input("Endpoint", value=os.getenv("STARDOG_ENDPOINT", "http://localhost:5820/nexus/query"))
        token     = st.text_input("Token", type="password", value=os.getenv("STARDOG_TOKEN", ""))
        db_name   = st.text_input("Database", value=os.getenv("STARDOG_DB", "nexus"))

    with st.expander("OpenAI", expanded=not st.session_state.connected):
        openai_key   = st.text_input("API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
        sparql_model = st.selectbox("SPARQL Model", ["o3-mini", "gpt-4o", "gpt-4o-mini"])
        answer_model = st.selectbox("Answer Model", ["gpt-4o", "gpt-4o-mini", "o3-mini"])

    if st.button("Connect", use_container_width=True):
        if endpoint and openai_key:
            try:
                # Set model preferences before resetting the settings singleton
                os.environ.update({"SPARQL_MODEL": sparql_model, "ANSWER_MODEL": answer_model})
                client = make_client(endpoint, token, openai_key, db_name)
                # Ping Stardog to validate credentials before proceeding
                client.query("ASK { ?s ?p ?o } LIMIT 1", inject_prefixes=False)
                from nexus.agents.session import create_session
                st.session_state.session_id = create_session("ui-user", "analyst")
                st.session_state.connected = True
                st.session_state["_conn_last_check"] = time.monotonic()
                st.success("Connected")
            except Exception as e:
                st.error(f"Connection failed: {e}")
                st.session_state.connected = False
                st.session_state["_conn_last_check"] = 0
        else:
            st.warning("Endpoint and API key required.")

    st.divider()
    st.markdown(f'<div style="color:{GREY_MUTED};font-size:.7rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-bottom:.4rem">Query Options</div>', unsafe_allow_html=True)
    use_virtual  = False
    show_sparql  = st.toggle("Show SPARQL", value=True)
    show_table   = st.toggle("Show Results Table", value=True)
    show_plan    = st.toggle("Show Query Plan", value=True)
    auto_confirm = st.toggle("Auto-confirm (skip HitL)", value=False)
    st.divider()

    st.divider()
    st.markdown(f'<div style="color:{GREY_MUTED};font-size:.7rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-bottom:.4rem">Demo</div>', unsafe_allow_html=True)
    demo_mode = st.toggle("Demo Mode", value=st.session_state.get("demo_mode", False), key="demo_mode")
    if demo_mode:
        demo_persona = st.selectbox(
            "Persona",
            ["Executive Board", "CTO", "CDTO", "Chief Architect"],
            key="demo_persona",
        )
        show_sparql  = False
        show_table   = False
        show_plan    = False
        auto_confirm = True
    st.divider()

    if st.button("Refresh Graph Health", use_container_width=True):
        if st.session_state.connected:
            from nexus.core.stardog_client import get_stardog
            db = get_stardog()
            checks = {
                "People":       "SELECT (COUNT(*) AS ?c) WHERE { ?s a hr:User }",
                "Apps":         "SELECT (COUNT(*) AS ?c) WHERE { ?s a app:Application }",
                "Data Assets":  "SELECT (COUNT(*) AS ?c) WHERE { ?s a data:Dataset }",
                "AI Agents":    "SELECT (COUNT(*) AS ?c) WHERE { ?s a ai:Agent }",
                "Open Findings":"SELECT (COUNT(*) AS ?c) WHERE { ?s a ops:AgentFinding ; ops:findingStatus 'Open' }",
            }
            for lbl, q in checks.items():
                try:
                    _, rows = db.to_rows(db.query(q))
                    st.metric(lbl, rows[0].get("c", "?") if rows else "?")
                except:
                    st.metric(lbl, "err")

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.update({"messages": [], "pending_plan": None, "pending_question": "", "turn_count": 0})
        st.rerun()
    st.caption("NEXUS v1.0 · Stardog + OpenAI · GSK")

# Identity defaults (removed from sidebar UI)
user_role = st.session_state.get("user_role", "analyst")
user_dept = ""
st.session_state["user_role"] = user_role

# ── Re-validate connection every 60 s with a 3-second timeout ────────
_CONN_CHECK_INTERVAL = 60
if st.session_state.connected:
    _now = time.monotonic()
    if _now - st.session_state.get("_conn_last_check", 0) > _CONN_CHECK_INTERVAL:
        try:
            import requests as _req
            from nexus.config.settings import settings as _s
            _cfg = _s.stardog
            _r = _req.post(
                _cfg.endpoint,
                data=b"ASK { ?s ?p ?o }",
                headers={
                    "Authorization": f"{_cfg.auth_scheme} {_cfg.token}",
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json",
                },
                verify=_cfg.verify_tls,
                timeout=3,
            )
            if _r.ok:
                st.session_state["_conn_last_check"] = time.monotonic()
            else:
                st.session_state.connected = False
                st.session_state["_conn_last_check"] = 0
        except Exception:
            st.session_state.connected = False
            st.session_state["_conn_last_check"] = 0

# ── Header ────────────────────────────────────────────────────────────
status_on  = st.session_state.connected
dot_class  = "on" if status_on else "off"
status_txt = "Connected" if status_on else "Disconnected"
sid        = st.session_state.session_id[:12] if st.session_state.session_id else "none"

st.markdown(
    f'<div class="nexus-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.5rem">'
    f'<div>'
    f'<div class="nexus-title">NEXUS <span>·</span> Enterprise Knowledge Graph</div>'
    f'<div class="nexus-sub">Conversational AI · Agent Grounding · Orchestration Intelligence · Semantic Governance · SA Advisor</div>'
    f'</div>'
    f'<div class="nexus-status">'
    f'<span class="nexus-status-dot {dot_class}"></span>'
    f'<span>{status_txt}</span>'
    f'<span style="color:{GREY_LINE};margin:0 .35rem">·</span>'
    f'<span>{user_role.title()}</span>'
    f'<span style="color:{GREY_LINE};margin:0 .35rem">·</span>'
    f'<span>Session <code style="background:{SURFACE_2};padding:.05rem .35rem;border-radius:3px">{sid}</code></span>'
    f'</div>'
    f'</div></div>',
    unsafe_allow_html=True
)

# ── Main tabs ─────────────────────────────────────────────────────────
tab_chat, tab_guided_sa, tab_sa, tab_data, tab_portfolio, tab_sa_health, tab_diagram, tab_impact, tab_ai_gov, tab_audit, tab_agent_tasks, tab_migration, tab_bsl, tab_gap = st.tabs(TAB_LABELS)


# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — KNOWLEDGE GRAPH CHAT
# ═══════════════════════════════════════════════════════════════════════
with tab_chat:

    EXAMPLES = [
        "Which applications directly support the Order-to-Cash business process?",
        "Which business capabilities have no application support in the current portfolio?",
        "What are all integration points between Finance and HR systems?",
        "Which data assets have no assigned data steward or owner?",
        "Which technology components are running end-of-life or unsupported software?",
        "Which business processes span more than one business domain with no shared data standard?",
    ]

    PERSONA_EXAMPLES = {
        "Executive Board": [
            "What percentage of our application portfolio is at risk?",
            "Which business capabilities have no technology support?",
            "What is our AI governance posture across all agents?",
            "Show me the top 5 applications recommended for decommission.",
            "What is the total portfolio health score?",
            "Which domains have the highest capability gaps?",
        ],
        "CTO": [
            "Which applications are on sunset or legacy lifecycle?",
            "What are the riskiest dependencies in our portfolio?",
            "Show me all AI agents without a risk tier assigned.",
            "Which capabilities are most over-served by redundant applications?",
            "What is the technical debt distribution across domains?",
            "List applications with the lowest technical fitness scores.",
        ],
        "CDTO": [
            "Which business capabilities support Order-to-Cash?",
            "What data assets does the Finance domain rely on?",
            "Show me capability gaps in the HR domain.",
            "Which applications enable our top 3 revenue-generating capabilities?",
            "What is the impact if we retire SAP ERP?",
            "Show me the transformation roadmap for the Supply Chain domain.",
        ],
        "Chief Architect": [
            "Generate a solution architecture for a new customer portal.",
            "What are the integration patterns between our ERP and CRM systems?",
            "List all Architecture Decision Records for the Finance domain.",
            "What is the blast radius if we decommission the legacy data warehouse?",
            "Show me the dependency graph for the Order Management application.",
            "Which applications violate our platform standards?",
        ],
    }

    _active_examples = (
        PERSONA_EXAMPLES.get(st.session_state.get("demo_persona", "Executive Board"), EXAMPLES)
        if st.session_state.get("demo_mode", False)
        else EXAMPLES
    )

    if not st.session_state.messages and not st.session_state.pending_plan:
        st.markdown(
            '<div style="color:#777777;font-size:.78rem;font-weight:600;letter-spacing:.05em;'
            'text-transform:uppercase;margin-bottom:.6rem">Example Questions</div>',
            unsafe_allow_html=True
        )
        cols = st.columns(3)
        for i, ex in enumerate(_active_examples):
            if cols[i % 3].button(ex[:58] + ("..." if len(ex) > 58 else ""), key=f"ex_{i}", use_container_width=True):
                st.session_state["prefill"] = ex
                st.rerun()

    # ── Chat history ───────────────────────────────────────────────
    for msg in st.session_state.messages:
        role   = msg["role"]
        avatar = ":material/hub:" if role == "assistant" else ":material/person:"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg["content"])
            if show_sparql and msg.get("sparql"):
                with st.expander("Generated SPARQL"):
                    st.code(msg["sparql"], language="sparql")
            if show_table and msg.get("rows"):
                st.dataframe(pd.DataFrame(msg["rows"]), use_container_width=True, hide_index=True)
            if msg.get("latency_ms"):
                st.caption(f"{msg['latency_ms']}ms · {msg.get('row_count', 0)} rows · {msg.get('model', '')}")

    # ── Render plan ────────────────────────────────────────────────
    def render_plan(plan):
        risk       = getattr(plan, "risk_level", "low")
        risk_class = {"low": "risk-low", "medium": "risk-medium", "high": "risk-high", "blocked": "risk-blocked"}.get(risk, "risk-low")
        conf       = int(getattr(plan, "confidence", 1.0) * 100)
        conf_col   = NEAR_BLACK if conf > 80 else GREY_DARK if conf > 50 else ORANGE_DARK

        def tags(items):
            return "".join(f'<span class="plan-tag">{i}</span>' for i in items) or "<span style='color:#555'>none</span>"

        warn_html = ""
        if getattr(plan, "security_notes", []):
            notes     = "".join(f"<div>- {n}</div>" for n in plan.security_notes)
            warn_html = f'<div class="plan-warn">Security notes:<br>{notes}</div>'

        assump_html = ""
        if getattr(plan, "assumptions", []):
            items       = "".join(f"<div style='color:#666666;font-size:.8rem;margin-top:.2rem'>- {a}</div>" for a in plan.assumptions)
            assump_html = f'<div style="margin-top:.6rem"><div class="plan-label">Assumptions</div>{items}</div>'

        html = (
            '<div class="plan-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.8rem">'
            f'<span style="color:#F36633;font-weight:600;font-size:.9rem">Query Plan</span>'
            f'<span class="{risk_class}">RISK: {risk.upper()}</span></div>'
            f'<div class="plan-label">Interpreted Intent</div>'
            f'<div class="plan-value">{getattr(plan, "interpreted_intent", "")}</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-top:.6rem">'
            f'<div><div class="plan-label">Domains</div>{tags(getattr(plan, "domains_involved", []))}</div>'
            f'<div><div class="plan-label">Confidence</div>'
            f'<div style="color:{conf_col};font-weight:600;font-size:.85rem">{conf}%</div>'
            f'<div class="confidence-bar" style="width:{conf}%;background:{conf_col}88"></div></div></div>'
            f'<div style="margin-top:.6rem"><div class="plan-label">Entities</div>{tags(getattr(plan, "mapped_entities", []))}</div>'
            f'<div style="margin-top:.4rem"><div class="plan-label">Relationships</div>{tags(getattr(plan, "mapped_relationships", []))}</div>'
            f'{assump_html}{warn_html}'
            '</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    # ── Execute pipeline ───────────────────────────────────────────
    def execute_query(question, clarification_context=""):
        from nexus.agents.guard        import check_intent, build_security_filter
        from nexus.core.nl_to_sparql   import nl_to_sparql
        from nexus.core.stardog_client  import get_stardog
        from nexus.core.answer_engine   import synthesise_full
        from nexus.audit.logger         import log_query, log_guard_event
        from nexus.audit.pii_scanner    import scan_and_redact
        from nexus.config.settings      import settings as _s

        t0         = time.monotonic()
        session_id = st.session_state.get("session_id", "")

        with st.chat_message("assistant", avatar=":material/hub:"):
            status = st.empty()

            status.markdown("Responsible AI check...")
            guard = check_intent(question, user_role)
            log_guard_event("ui-user", question, guard.allowed, guard.risk_level.value, guard.flags)
            if not guard.allowed:
                msg = f"Blocked: {guard.reason}"
                if guard.flags: msg += " | Flags: " + ", ".join(guard.flags)
                status.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                return
            if guard.risk_level.value in ("medium", "high"):
                st.warning(f"Risk {guard.risk_level.value.upper()}: {guard.reason}")

            sec = build_security_filter(user_role, user_dept)

            status.markdown("Generating SPARQL...")
            try:
                sparql = nl_to_sparql(
                    question, clarification_context=clarification_context,
                    user_role=user_role, use_virtual_graph=use_virtual,
                    extra_filters=sec.sparql_data_filter,
                    session_id=session_id,
                )
            except Exception as exc:
                msg = f"SPARQL generation failed: {exc}"
                status.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                return

            db         = get_stardog()
            complexity = db.estimate_complexity(sparql)
            if complexity > _s.security.max_sparql_complexity:
                msg = f"Query complexity {complexity} exceeds limit {_s.security.max_sparql_complexity}. Simplify."
                status.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                return

            status.markdown("Querying knowledge graph...")
            try:
                raw     = db.query(sparql)
                columns, rows = db.to_rows(raw)
                from nexus.core.sparql_feedback import record_success
                record_success(question, sparql, len(rows))
            except Exception as exc:
                from nexus.core.sparql_feedback import record_failure
                record_failure(question, sparql, str(exc))
                _exc_str = str(exc).lower()
                if any(w in _exc_str for w in ("401", "403", "unauthorized", "forbidden", "connection", "timeout", "ssl")):
                    st.session_state.connected = False
                    st.session_state["_conn_validated"] = False
                msg = f"Query failed: {exc}"
                status.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                return

            total           = len(rows)
            rows            = rows[:sec.max_rows]
            scan            = scan_and_redact(rows, redact=True)
            classifications = list({r.get("classification", "") for r in rows if r.get("classification")})

            status.markdown("Synthesising answer...")
            result  = synthesise_full(
                question, columns, scan.redacted_rows, sparql, total,
                user_role=user_role, session_id=session_id,
            )
            answer  = result.answer
            latency = int((time.monotonic() - t0) * 1000)

            model_used = (
                _s.anthropic.answer_model if _s.anthropic.enabled
                else _s.openai.answer_model
            )
            log_query("ui-user", user_role, session_id, question, sparql,
                      len(rows), columns, classifications, latency, model_used,
                      pii_detected=scan.pii_found)

            # Persist turn for multi-turn context
            if session_id:
                try:
                    from nexus.agents.session import store_turn, get_session_context, update_session
                    ctx   = get_session_context(session_id)
                    tnum  = ctx.get("turn_count", 0) + 1
                    focus = [r.get("uri") or r.get("app") or "" for r in scan.redacted_rows[:5] if isinstance(r, dict)]
                    focus = [f for f in focus if f.startswith("http") or f.startswith("urn")]
                    update_session(session_id, question, focus, tnum)
                    store_turn(session_id, tnum, question, answer[:2000])
                except Exception:
                    pass

            status.empty()
            if scan.pii_found:
                det = ", ".join(f"{d['field']} ({d['type']})" for d in scan.detections)
                st.info(f"PII detected and redacted: {det}")

            st.markdown(answer)

            if show_sparql:
                with st.expander("Generated SPARQL"):
                    st.code(sparql, language="sparql")
            if show_table and scan.redacted_rows:
                label = f"Results — {total} rows"
                if total > sec.max_rows: label += f" (showing {sec.max_rows})"
                with st.expander(label):
                    st.dataframe(pd.DataFrame(scan.redacted_rows), use_container_width=True, hide_index=True)

            st.caption(
                f"{latency}ms · {total} rows"
                + (" · PII redacted" if scan.pii_found else "")
                + f" · complexity:{complexity} · {model_used}"
            )

            # Follow-up suggestion chips
            if result.suggestions:
                st.markdown(
                    '<div style="margin-top:.6rem;font-size:.72rem;font-weight:600;'
                    'letter-spacing:.06em;text-transform:uppercase;color:#888;margin-bottom:.3rem">'
                    'Follow-up questions</div>',
                    unsafe_allow_html=True
                )
                chip_cols = st.columns(len(result.suggestions))
                for ci, sug in enumerate(result.suggestions):
                    if chip_cols[ci].button(sug, key=f"sug_{st.session_state.turn_count}_{ci}",
                                            use_container_width=True):
                        st.session_state["prefill"] = sug
                        st.rerun()

            st.session_state.messages.append({
                "role": "assistant", "content": answer,
                "sparql": sparql, "rows": scan.redacted_rows[:50],
                "row_count": total, "latency_ms": latency, "model": model_used,
            })
            st.session_state.turn_count += 1

    # ── HitL plan confirmation ─────────────────────────────────────
    def handle_pending():
        plan     = st.session_state.pending_plan
        question = st.session_state.pending_question
        if show_plan:
            render_plan(plan)
        cqs = getattr(plan, "clarifying_questions", [])
        with st.chat_message("assistant", avatar=":material/hub:"):
            if cqs and not getattr(plan, "ready_to_execute", True) and not auto_confirm:
                st.markdown("Please clarify before I run this query:")
                answers = []
                with st.form("clarify_form", clear_on_submit=True):
                    for i, cq in enumerate(cqs[:2]):
                        answers.append(st.text_input(f"Q{i+1}: {cq}", key=f"cq_ans_{i}"))
                    c1, c2 = st.columns(2)
                    submitted = c1.form_submit_button("Submit & Run", use_container_width=True)
                    skipped   = c2.form_submit_button("Skip & Run",   use_container_width=True)
                if submitted or skipped:
                    ctx = ""
                    if submitted and any(a.strip() for a in answers):
                        ctx = "\n\n".join(
                            f"Q: {cqs[i]}\nA: {answers[i]}"
                            for i in range(len(cqs)) if i < len(answers) and answers[i].strip()
                        )
                    st.session_state.pending_plan     = None
                    st.session_state.pending_question = ""
                    execute_query(question, ctx)
            else:
                if not auto_confirm:
                    st.markdown("Query plan confirmed. Ready to execute.")
                    c1, c2 = st.columns(2)
                    if c1.button("Run Query",     use_container_width=True, key="btn_run"):
                        st.session_state.pending_plan = None
                        execute_query(question, st.session_state.pending_clarification)
                    if c2.button("Edit Question", use_container_width=True, key="btn_edit"):
                        st.session_state.pending_plan     = None
                        st.session_state.pending_question = ""
                        st.rerun()
                else:
                    st.session_state.pending_plan = None
                    execute_query(question, st.session_state.pending_clarification)

    if st.session_state.pending_plan:
        handle_pending()

    # ── Chat input ─────────────────────────────────────────────────
    prefill  = st.session_state.pop("prefill", "")
    question = st.chat_input("Ask NEXUS anything about your enterprise...") or prefill

    if question and not st.session_state.pending_plan:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(question)

        if not st.session_state.connected:
            with st.chat_message("assistant", avatar=":material/hub:"):
                st.warning("Connect to NEXUS via the sidebar first.")
        else:
            with st.chat_message("assistant", avatar=":material/hub:"):
                with st.spinner("Mapping to ontology..."):
                    try:
                        from nexus.core.clarifier import clarify
                        from nexus.agents.guard   import check_intent
                        guard = check_intent(question, user_role)
                        if not guard.allowed:
                            msg = f"Blocked: {guard.reason}"
                            st.markdown(msg)
                            st.session_state.messages.append({"role": "assistant", "content": msg})
                            st.stop()
                        if auto_confirm:
                            st.session_state.pending_plan = None
                            execute_query(question)
                        else:
                            plan = clarify(question, user_role)
                            plan.risk_level                    = guard.risk_level.value
                            st.session_state.pending_plan      = plan
                            st.session_state.pending_question  = question
                            st.session_state.pending_clarification = ""
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Clarification failed ({exc}). Running directly.")
                        execute_query(question)



# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — GUIDED SA ADVISOR
# ═══════════════════════════════════════════════════════════════════════
with tab_guided_sa:
    try:
        from nexus.ui.guided_sa_tab import render_guided_sa_tab
        render_guided_sa_tab(st, user_role=user_role)
    except Exception as exc:
        st.error(f"Solution Architect AI Agent failed to load: {exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — SA ADVISOR (ArchiMate + Anthropic API)
# ═══════════════════════════════════════════════════════════════════════
with tab_sa:

    st.caption('Use Solution Architect AI Agent for capability-first architecture interviews. Use this tab for freeform EA artifact generation.')

    # ── ArchiMate definitions ──────────────────────────────────────
    LAYER_ORDER = ["Motivation", "Business", "Application", "Technology"]

    # Strict-palette ArchiMate layers: depth of grey + orange accent encodes
    # the layer (deeper grey = higher / more abstract layer).
    LAYER_COLORS = {
        "Motivation":  {"band": NEAR_BLACK, "border": GREY_DARK,  "accent": ORANGE},
        "Business":    {"band": GREY_DARK,  "border": GREY_TEXT,  "accent": ORANGE_LIGHT},
        "Application": {"band": GREY_TEXT,  "border": GREY_LINE,  "accent": ORANGE},
        "Technology":  {"band": GREY_MUTED, "border": GREY_LINE,  "accent": ORANGE_LIGHT},
    }

    ELEMENT_DEFS = {
        "BusinessActor":        {"layer": "Business",    "label": "Business Actor"},
        "BusinessRole":         {"layer": "Business",    "label": "Business Role"},
        "BusinessProcess":      {"layer": "Business",    "label": "Business Process"},
        "BusinessFunction":     {"layer": "Business",    "label": "Business Function"},
        "BusinessService":      {"layer": "Business",    "label": "Business Service"},
        "BusinessObject":       {"layer": "Business",    "label": "Business Object"},
        "ApplicationComponent": {"layer": "Application", "label": "App Component"},
        "ApplicationService":   {"layer": "Application", "label": "App Service"},
        "ApplicationInterface": {"layer": "Application", "label": "App Interface"},
        "DataObject":           {"layer": "Application", "label": "Data Object"},
        "Node":                 {"layer": "Technology",  "label": "Node"},
        "SystemSoftware":       {"layer": "Technology",  "label": "System Software"},
        "TechnologyService":    {"layer": "Technology",  "label": "Tech Service"},
        "Artifact":             {"layer": "Technology",  "label": "Artifact"},
        "Driver":               {"layer": "Motivation",  "label": "Driver"},
        "Goal":                 {"layer": "Motivation",  "label": "Goal"},
        "Principle":            {"layer": "Motivation",  "label": "Principle"},
        "Requirement":          {"layer": "Motivation",  "label": "Requirement"},
    }

    # Strict-palette relationship styling — line dash + orange/grey shade
    # encodes the relationship type.
    REL_STYLES = {
        "ServingRelationship":     {"dash": "none",  "color": ORANGE},
        "RealizationRelationship": {"dash": "6,4",   "color": ORANGE_LIGHT},
        "CompositionRelationship": {"dash": "none",  "color": NEAR_BLACK},
        "AggregationRelationship": {"dash": "none",  "color": GREY_DARK},
        "FlowRelationship":        {"dash": "4,4",   "color": ORANGE},
        "TriggeringRelationship":  {"dash": "none",  "color": NEAR_BLACK},
        "AccessRelationship":      {"dash": "3,3",   "color": GREY_MUTED},
        "AssociationRelationship": {"dash": "none",  "color": GREY_TEXT},
        "InfluenceRelationship":   {"dash": "8,4",   "color": ORANGE_DARK},
    }

    SA_SYSTEM = """You are a senior Enterprise Architect expert in ArchiMate 3.1.

Generate an ArchiMate diagram and professional SA advisory. Return ONLY valid JSON, no markdown fences:
{
  "title": "Concise descriptive title",
  "advisory": "4 paragraphs separated by newlines: 1) Architecture overview 2) Key design decisions and rationale 3) Risks and mitigations 4) Strategic recommendations. Professional EA language. Specific and actionable.",
  "elements": [{"id":"e1","type":"ElementType","label":"Short Label","description":"One sentence.","layer":"LayerName"}],
  "relationships": [{"id":"r1","from":"e1","to":"e2","type":"RelationshipType","label":""}]
}

Valid element types:
- Business layer: BusinessActor, BusinessRole, BusinessProcess, BusinessFunction, BusinessService, BusinessObject
- Application layer: ApplicationComponent, ApplicationService, ApplicationInterface, DataObject
- Technology layer: Node, SystemSoftware, TechnologyService, Artifact
- Motivation layer: Driver, Goal, Principle, Requirement

Valid relationship types: ServingRelationship, RealizationRelationship, CompositionRelationship, FlowRelationship, TriggeringRelationship, AccessRelationship, AssociationRelationship, AggregationRelationship, InfluenceRelationship

Rules: 6-14 elements across 2-4 layers. 4-12 relationships. Labels max 4 words. Always populate the layer field using the layer name. Return ONLY JSON."""

    SA_EXAMPLES = [
        "NEXUS AI agent governance with data stewardship",
        "Enterprise data mesh with federated governance",
        "Cloud-native microservices with API gateway",
        "Zero trust security for hybrid cloud",
        "AI orchestration pipeline with responsible AI controls",
        "GSK clinical data platform with regulatory compliance",
    ]

    # ── SA call to Anthropic API via requests ──────────────────────
    def call_sa_api(prompt: str) -> dict:
        import requests as req
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            # Fallback: try OpenAI key env var name (user might have set it)
            anthropic_key = os.getenv("CLAUDE_API_KEY", "")
        if not anthropic_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file: ANTHROPIC_API_KEY=sk-ant-..."
            )
        # Zscaler corporate SSL interception: hardcode verify=False to match the
        # Stardog and Databricks clients. Shell env vars SSL_CERT_FILE /
        # REQUESTS_CA_BUNDLE are deliberately ignored because they point at
        # corp-specific bundles that don't include the Anthropic API chain.
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 3000,
                "system": SA_SYSTEM,
                "messages": [{"role": "user", "content": f"Architecture to diagram: {prompt}"}],
            },
            timeout=60,
            verify=False,
        )
        if not resp.ok:
            raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        raw  = data.get("content", [{}])[0].get("text", "")
        raw  = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    # ── draw.io XML export ─────────────────────────────────────────
    def build_drawio_xml(result: dict, pos: dict, W: int, H: int) -> str:
        xml = '<?xml version="1.0" encoding="UTF-8"?><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        for el_id, el in pos.items():
            lc = LAYER_COLORS.get(el.get("layer", "Application"), LAYER_COLORS["Application"])
            xml += (
                f'<mxCell id="{el_id}" value="{el["label"]}" '
                f'style="rounded=1;fillColor={lc["band"]};strokeColor={lc["border"]};'
                f'fontColor=#FFFFFF;fontSize=11;fontStyle=1;" '
                f'vertex="1" parent="1">'
                f'<mxGeometry x="{el["x"]}" y="{el["y"]}" width="{el["w"]}" height="{el["h"]}" as="geometry"/>'
                f'</mxCell>'
            )
        for rel in result.get("relationships", []):
            rs = REL_STYLES.get(rel["type"], REL_STYLES["AssociationRelationship"])
            xml += (
                f'<mxCell id="{rel["id"]}" value="{rel.get("label","")}" '
                f'style="edgeStyle=orthogonalEdgeStyle;strokeColor={rs["color"]};'
                f'dashed={1 if rs["dash"] != "none" else 0};fontColor={rs["color"]};fontSize=9;" '
                f'edge="1" source="{rel["from"]}" target="{rel["to"]}" parent="1">'
                f'<mxGeometry relative="1" as="geometry"/></mxCell>'
            )
        xml += "</root></mxGraphModel>"
        return xml

    # ── Layout engine ──────────────────────────────────────────────
    def layout_elements(elements: list) -> tuple[dict, dict, int, int]:
        EW, EH, GX, GY, COLS = 160, 64, 24, 16, 4
        BPAD_T, BPAD_B, BGAP, SPAD = 44, 20, 12, 24

        by_layer = {l: [] for l in LAYER_ORDER}
        for el in elements:
            layer = el.get("layer") or ELEMENT_DEFS.get(el["type"], {}).get("layer", "Application")
            el = dict(el, layer=layer)
            by_layer[layer].append(el)

        pos, bands = {}, {}
        y = 12
        for lyr in LAYER_ORDER:
            els = by_layer[lyr]
            if not els:
                continue
            band_y = y
            y += BPAD_T
            rows = max(1, (len(els) + COLS - 1) // COLS)
            for i, el in enumerate(els):
                pos[el["id"]] = {
                    **el,
                    "x": SPAD + (i % COLS) * (EW + GX),
                    "y": y + (i // COLS) * (EH + GY),
                    "w": EW, "h": EH,
                }
            band_h = BPAD_T + rows * EH + (rows - 1) * GY + BPAD_B
            bands[lyr] = {"y": band_y, "h": band_h}
            y += rows * EH + (rows - 1) * GY + BPAD_B + BGAP

        vals = list(pos.values())
        W = (max(v["x"] + v["w"] for v in vals) + SPAD) if vals else 600
        H = y + 12
        return pos, bands, W, H

    # ── SVG diagram renderer ───────────────────────────────────────
    def render_sa_diagram(result: dict) -> str:
        elements = result.get("elements", [])
        rels     = result.get("relationships", [])
        pos, bands, W, H = layout_elements(elements)

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'style="background:#F7F7F7;display:block;font-family:DM Sans,sans-serif;">'
        ]

        # Layer bands
        for lyr, b in bands.items():
            lc = LAYER_COLORS[lyr]
            svg_parts.append(
                f'<rect x="0" y="{b["y"]}" width="{W}" height="{b["h"]}" fill="{lc["band"]}" opacity="0.8"/>'
                f'<rect x="0" y="{b["y"]}" width="3" height="{b["h"]}" fill="{lc["border"]}"/>'
                f'<text x="10" y="{b["y"]+26}" font-family="DM Mono,monospace" font-size="9" '
                f'font-weight="600" fill="{lc["accent"]}" opacity="0.9" letter-spacing="0.1em">'
                f'{lyr.upper()} LAYER</text>'
            )

        # Relationships
        for rel in rels:
            frm = pos.get(rel.get("from"))
            to  = pos.get(rel.get("to"))
            if not frm or not to:
                continue
            rs = REL_STYLES.get(rel["type"], REL_STYLES["AssociationRelationship"])

            fi = LAYER_ORDER.index(frm.get("layer","Application")) if frm.get("layer") in LAYER_ORDER else 2
            ti = LAYER_ORDER.index(to.get("layer","Application"))  if to.get("layer") in LAYER_ORDER else 2

            if fi != ti:
                x1 = frm["x"] + frm["w"] // 2
                y1 = frm["y"] + frm["h"] if fi < ti else frm["y"]
                x2 = to["x"]  + to["w"]  // 2
                y2 = to["y"]  if fi < ti else to["y"] + to["h"]
            elif frm["x"] < to["x"]:
                x1, y1 = frm["x"] + frm["w"], frm["y"] + frm["h"] // 2
                x2, y2 = to["x"],             to["y"]  + to["h"]  // 2
            else:
                x1, y1 = frm["x"],            frm["y"] + frm["h"] // 2
                x2, y2 = to["x"] + to["w"],   to["y"]  + to["h"]  // 2

            cx1, cy1 = x1 + (x2 - x1) * 0.3, y1
            cx2, cy2 = x1 + (x2 - x1) * 0.7, y2
            dash_attr = f'stroke-dasharray="{rs["dash"]}"' if rs["dash"] != "none" else ""
            svg_parts.append(
                f'<path d="M{x1},{y1} C{cx1},{cy1} {cx2},{cy2} {x2},{y2}" '
                f'fill="none" stroke="{rs["color"]}" stroke-width="1.5" {dash_attr} opacity="0.7"/>'
            )
            # Arrowhead
            import math
            angle = math.atan2(y2 - cy2, x2 - cx2)
            L, W2 = 9, 4.5
            p1x = x2 - L * math.cos(angle - 0.5)
            p1y = y2 - L * math.sin(angle - 0.5)
            p2x = x2 - L * math.cos(angle + 0.5)
            p2y = y2 - L * math.sin(angle + 0.5)
            svg_parts.append(
                f'<polygon points="{x2},{y2} {p1x:.1f},{p1y:.1f} {p2x:.1f},{p2y:.1f}" '
                f'fill="{rs["color"]}" opacity="0.85"/>'
            )
            if rel.get("label"):
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 6
                svg_parts.append(
                    f'<text x="{mx:.0f}" y="{my:.0f}" text-anchor="middle" '
                    f'font-family="DM Mono,monospace" font-size="8" fill="{rs["color"]}" opacity="0.85">'
                    f'{rel["label"]}</text>'
                )

        # Elements
        for el_id, el in pos.items():
            lc   = LAYER_COLORS.get(el.get("layer", "Application"), LAYER_COLORS["Application"])
            edef = ELEMENT_DEFS.get(el["type"], {"label": el["type"]})
            cx   = el["x"] + el["w"] // 2
            cy   = el["y"] + el["h"] // 2 + 5
            svg_parts.append(
                f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["w"]}" height="{el["h"]}" '
                f'rx="4" fill="#FFFFFF" stroke="{lc["border"]}" stroke-width="1"/>'
                f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["w"]}" height="2" '
                f'rx="1" fill="{lc["accent"]}" opacity="0.5"/>'
                f'<text x="{el["x"]+6}" y="{el["y"]+14}" font-family="DM Mono,monospace" '
                f'font-size="8" fill="{lc["accent"]}" opacity="0.7">{edef["label"]}</text>'
                f'<text x="{cx}" y="{cy}" text-anchor="middle" font-family="DM Sans,sans-serif" '
                f'font-size="11" font-weight="600" fill="#1A1A1A">{el["label"]}</text>'
            )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    # ─────────────────────────────────────────────────────────────
    # SA Advisor UI
    # ─────────────────────────────────────────────────────────────

    st.markdown(
        '<div style="color:#777777;font-size:.72rem;font-weight:700;letter-spacing:.1em;'
        'text-transform:uppercase;margin-bottom:.6rem">SA Advisor · ArchiMate 3.1 Generator</div>',
        unsafe_allow_html=True
    )

    # Prompt input — example chips pre-fill via a "_pending" key that we copy
    # into the widget's slot BEFORE the widget renders, since Streamlit forbids
    # writing to a widget key after it has been instantiated on the same run.
    if "_sa_pending_prompt" in st.session_state:
        st.session_state.sa_prompt_input = st.session_state.pop("_sa_pending_prompt")
    elif "sa_prompt_input" not in st.session_state:
        st.session_state.sa_prompt_input = st.session_state.sa_prompt

    sa_prompt = st.text_area(
        "Architecture description",
        placeholder="Describe your architecture… e.g. 'NEXUS AI agent governance with data stewardship and audit controls'",
        height=80,
        key="sa_prompt_input",
        label_visibility="collapsed",
    )

    col_btn, col_hint = st.columns([1, 4])
    with col_btn:
        generate_btn = st.button("Generate Diagram →", use_container_width=True, key="sa_generate")
    with col_hint:
        st.markdown(
            '<div style="color:#777777;font-size:.78rem;padding-top:.5rem">'
            'Powered by Claude via Anthropic API · Requires <code>ANTHROPIC_API_KEY</code> in .env</div>',
            unsafe_allow_html=True
        )

    # Example chips
    st.markdown('<div style="margin:.3rem 0 .6rem;color:#777777;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;font-weight:600">Examples</div>', unsafe_allow_html=True)
    ex_cols = st.columns(3)
    for i, ex in enumerate(SA_EXAMPLES):
        if ex_cols[i % 3].button(ex, key=f"sa_ex_{i}", use_container_width=True):
            st.session_state.sa_prompt = ex
            st.session_state["_sa_pending_prompt"] = ex
            st.rerun()

    st.divider()

    # ── Generate ───────────────────────────────────────────────────
    if generate_btn and sa_prompt.strip():
        with st.spinner("Generating ArchiMate diagram via Claude…"):
            try:
                st.session_state.sa_result = call_sa_api(sa_prompt.strip())
                st.session_state.sa_prompt = sa_prompt.strip()
            except Exception as exc:
                st.error(f"Generation failed: {exc}")

    result = st.session_state.sa_result

    if result:
        elements = result.get("elements", [])
        rels     = result.get("relationships", [])
        pos, bands, svgW, svgH = layout_elements(elements)

        # Title
        st.markdown(
            f'<div style="font-size:1.1rem;font-weight:700;color:#1A1A1A;margin-bottom:1rem;'
            f'letter-spacing:-.01em">{result.get("title","Untitled Architecture")}</div>',
            unsafe_allow_html=True
        )

        diagram_tab, advisory_tab, elements_tab, export_tab = st.tabs([
            "Diagram", "SA Advisory", "Elements & Relations", "Export"
        ])

        with diagram_tab:
            svg_html = render_sa_diagram(result)
            st.markdown(
                f'<div style="overflow-x:auto;background:#F7F7F7;border:1px solid #D8D8D8;'
                f'border-radius:8px;padding:12px">{svg_html}</div>',
                unsafe_allow_html=True
            )
            # Legend
            legend_items = "".join(
                f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:16px;">'
                f'<span style="width:10px;height:10px;border-radius:2px;background:{lc["accent"]};opacity:.8;display:inline-block"></span>'
                f'<span style="color:{lc["accent"]};font-size:10px;font-family:DM Mono,monospace">{lyr}</span>'
                f'</span>'
                for lyr, lc in LAYER_COLORS.items()
            )
            rel_items = "".join(
                f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px;">'
                f'<svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="{rs["color"]}" '
                f'stroke-width="1.5" {"stroke-dasharray=" + repr(rs["dash"]) if rs["dash"] != "none" else ""}/></svg>'
                f'<span style="color:#777777;font-size:9px">{rtype.replace("Relationship","")}</span>'
                f'</span>'
                for rtype, rs in list(REL_STYLES.items())[:5]
            )
            st.markdown(
                f'<div style="margin-top:8px;padding:6px 0;border-top:1px solid #D8D8D8;display:flex;flex-wrap:wrap;gap:4px">'
                f'{legend_items}{rel_items}</div>',
                unsafe_allow_html=True
            )

        with advisory_tab:
            advisory = result.get("advisory", "")
            paragraphs = [p.strip() for p in advisory.split("\n") if p.strip()]
            section_labels = [
                "Architecture Overview",
                "Design Decisions & Rationale",
                "Risks & Mitigations",
                "Strategic Recommendations",
            ]
            for i, para in enumerate(paragraphs):
                label = section_labels[i] if i < len(section_labels) else f"Section {i+1}"
                st.markdown(
                    f'<div class="sa-advisory-section">'
                    f'<div class="sa-section-label">{label}</div>'
                    f'<div style="color:#444444;font-size:.88rem;line-height:1.75">{para}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        with elements_tab:
            st.markdown('<div class="sa-section-label" style="margin-bottom:.5rem">Elements by Layer</div>', unsafe_allow_html=True)
            for lyr in LAYER_ORDER:
                els_in_layer = [e for e in elements if (e.get("layer") or ELEMENT_DEFS.get(e["type"], {}).get("layer")) == lyr]
                if not els_in_layer:
                    continue
                lc = LAYER_COLORS[lyr]
                st.markdown(
                    f'<div style="font-size:.72rem;font-weight:700;letter-spacing:.08em;color:{lc["accent"]};'
                    f'text-transform:uppercase;margin:.8rem 0 .3rem">{lyr} Layer</div>',
                    unsafe_allow_html=True
                )
                for el in els_in_layer:
                    edef = ELEMENT_DEFS.get(el["type"], {"label": el["type"]})
                    st.markdown(
                        f'<div class="sa-detail-card sa-layer-band-{lyr}">'
                        f'<div style="display:flex;justify-content:space-between;margin-bottom:.2rem">'
                        f'<span style="color:#1A1A1A;font-weight:600;font-size:.85rem">{el["label"]}</span>'
                        f'<span style="color:{lc["accent"]};font-size:.72rem;font-family:DM Mono,monospace">{edef["label"]}</span>'
                        f'</div>'
                        f'<div style="color:#666666;font-size:.8rem">{el.get("description","")}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

            st.markdown('<div class="sa-section-label" style="margin:.8rem 0 .4rem">Relationships</div>', unsafe_allow_html=True)
            for rel in rels:
                rs       = REL_STYLES.get(rel["type"], REL_STYLES["AssociationRelationship"])
                from_el  = next((e for e in elements if e["id"] == rel["from"]), {})
                to_el    = next((e for e in elements if e["id"] == rel["to"]),   {})
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:.3rem 0;border-bottom:1px solid #EBEBEB;">'
                    f'<span style="color:#333333;font-size:.82rem;min-width:120px">{from_el.get("label","?")}</span>'
                    f'<span style="color:{rs["color"]};font-family:DM Mono,monospace;font-size:.72rem;flex:1">──{rel.get("label","")or rel["type"].replace("Relationship","")}──▶</span>'
                    f'<span style="color:#333333;font-size:.82rem;min-width:120px;text-align:right">{to_el.get("label","?")}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        with export_tab:
            st.markdown('<div class="sa-section-label" style="margin-bottom:.8rem">Export Options</div>', unsafe_allow_html=True)

            col_dx, col_sx = st.columns(2)

            with col_dx:
                drawio_xml = build_drawio_xml(result, pos, svgW, svgH)
                st.download_button(
                    label=f"{mat('download')}  Download draw.io XML",
                    data=drawio_xml,
                    file_name=f"{result.get('title','nexus-arch').replace(' ','_')}.drawio",
                    mime="application/xml",
                    use_container_width=True,
                )
                st.caption("Open in diagrams.net or draw.io — full ArchiMate shape library")

            with col_sx:
                svg_data = render_sa_diagram(result)
                st.download_button(
                    label=f"{mat('download')}  Download SVG",
                    data=svg_data,
                    file_name=f"{result.get('title','nexus-arch').replace(' ','_')}.svg",
                    mime="image/svg+xml",
                    use_container_width=True,
                )
                st.caption("Scalable vector graphic for documentation or presentations")

            st.markdown('<div class="sa-section-label" style="margin:.8rem 0 .4rem">Raw JSON</div>', unsafe_allow_html=True)
            st.code(json.dumps(result, indent=2), language="json")

    else:
        st.markdown(
            f'<div style="text-align:center;padding:3rem 1rem;color:{GREY_DARK};">'
            f'<div style="margin-bottom:.8rem;color:{GREY_LINE}">{icon("building", size=44, color=GREY_LINE)}</div>'
            f'<div style="font-size:.95rem;font-weight:600;color:{GREY_TEXT};margin-bottom:.4rem">No diagram generated yet</div>'
            f'<div style="font-size:.82rem">Enter an architecture description above and click <strong style="color:{ORANGE}">Generate Diagram</strong></div>'
            f'</div>',
            unsafe_allow_html=True
        )


# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — DATA QUERY (Text2SQL over Unity Catalog metadata)
# ═══════════════════════════════════════════════════════════════════════
with tab_data:
    try:
        from nexus.core.databricks_client import get_databricks
        from nexus.core.stardog_client import get_stardog as _get_stardog
        from nexus.ui.data_query_tab import render_data_query_tab
        _connected = st.session_state.get("connected", False)
        _stardog   = _get_stardog() if _connected else None
        _dbx       = get_databricks() if _connected else None
        render_data_query_tab(stardog=_stardog, databricks=_dbx)
    except Exception as _exc:
        st.error(f"Data Query tab failed to load: {_exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 5 — PORTFOLIO INTELLIGENCE (APM TIME model)
# ═══════════════════════════════════════════════════════════════════════
with tab_portfolio:
    try:
        from nexus.ui.portfolio_tab import render_portfolio_tab
        render_portfolio_tab(
            connected=st.session_state.get("connected", False),
            user_role=st.session_state.get("user_role", "analyst"),
        )
    except Exception as _exc:
        st.error(f"Portfolio Intelligence tab failed to load: {_exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 6 — SA PORTFOLIO HEALTH
# ═══════════════════════════════════════════════════════════════════════
with tab_sa_health:
    try:
        from nexus.ui.sa_health_tab import render_sa_health_tab
        render_sa_health_tab(
            connected=st.session_state.get("connected", False),
            user_role=st.session_state.get("user_role", "analyst"),
        )
    except Exception as _exc:
        st.error(f"SA Health tab failed to load: {_exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 7 — ARCHITECTURE DIAGRAM STUDIO
# ═══════════════════════════════════════════════════════════════════════
with tab_diagram:
    try:
        from nexus.ui.diagram_tab import render_diagram_tab
        render_diagram_tab(
            connected=st.session_state.get("connected", False),
            user_role=st.session_state.get("user_role", "analyst"),
        )
    except Exception as _exc:
        st.error(f"Architecture Diagrams tab failed to load: {_exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 8 — CHANGE IMPACT RADAR
# ═══════════════════════════════════════════════════════════════════════
with tab_impact:
    try:
        from nexus.ui.impact_tab import render_impact_tab
        render_impact_tab(
            connected=st.session_state.get("connected", False),
            user_role=st.session_state.get("user_role", "analyst"),
        )
    except Exception as _exc:
        st.error(f"Change Impact tab failed to load: {_exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 9 — AI AGENT GOVERNANCE CONSOLE
# ═══════════════════════════════════════════════════════════════════════
with tab_ai_gov:
    try:
        from nexus.ui.ai_governance_tab import render_ai_governance_tab
        render_ai_governance_tab(
            connected=st.session_state.get("connected", False),
            user_role=st.session_state.get("user_role", "analyst"),
        )
    except Exception as _exc:
        st.error(f"AI Governance tab failed to load: {_exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 10 — AUDIT & OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════
with tab_audit:
    try:
        from nexus.ui.audit_tab import render_audit_tab
        render_audit_tab(user_role=st.session_state.get("user_role", "analyst"))
    except Exception as _exc:
        st.error(f"Audit tab failed to load: {_exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 11 — AGENT TASKS (Multi-agent orchestration monitor)
# ═══════════════════════════════════════════════════════════════════════
with tab_agent_tasks:
    from nexus.ui.theme import ORANGE, GREY_MUTED, GREY_LINE, NEAR_BLACK, WHITE, SURFACE_2

    st.markdown(
        '<div style="color:#777777;font-size:.72rem;font-weight:700;letter-spacing:.1em;'
        'text-transform:uppercase;margin-bottom:.6rem">Autonomous Agent Tasks</div>',
        unsafe_allow_html=True
    )

    # ── Submit new task ────────────────────────────────────────────
    with st.expander("Submit New Orchestrator Task", expanded=True):
        task_desc = st.text_area(
            "Task description",
            placeholder=(
                "Describe a high-level EA task — e.g. 'Run a full portfolio health check, "
                "identify top 5 Eliminate candidates, analyse their change impact, and create findings.'"
            ),
            height=100,
            key="agent_task_desc",
            label_visibility="collapsed",
        )
        if st.button("Submit Task →", use_container_width=False, key="agent_task_submit"):
            if not task_desc.strip():
                st.warning("Please enter a task description.")
            elif not st.session_state.get("connected"):
                st.warning("Connect to NEXUS first (sidebar).")
            else:
                try:
                    from nexus.agents.orchestrator import submit_task
                    tid = submit_task(
                        description=task_desc.strip(),
                        user_id="ui-user",
                        user_role=st.session_state.get("user_role", "analyst"),
                    )
                    st.success(f"Task submitted: `{tid}` — refresh below to track progress.")
                except Exception as _exc:
                    st.error(f"Task submission failed: {_exc}")

    st.divider()

    # ── Task list ──────────────────────────────────────────────────
    col_refresh, col_spacer = st.columns([1, 5])
    with col_refresh:
        refresh_tasks = st.button("Refresh Tasks", use_container_width=True, key="agent_task_refresh")

    try:
        from nexus.agents.orchestrator import list_tasks
        tasks = list_tasks(user_id="ui-user", limit=20)
    except Exception as _exc:
        st.error(f"Could not load tasks: {_exc}")
        tasks = []

    STATUS_COLORS = {
        "pending":   "#888888",
        "running":   "#F36633",
        "completed": "#22C55E",
        "failed":    "#EF4444",
        "cancelled": "#9CA3AF",
    }

    if not tasks:
        st.markdown(
            f'<div style="text-align:center;padding:2rem;color:{GREY_MUTED};font-size:.88rem">'
            f'No tasks yet. Submit a task above to get started.</div>',
            unsafe_allow_html=True
        )
    else:
        for task in tasks:
            status_color = STATUS_COLORS.get(task.get("status", ""), "#888")
            sub_tasks    = task.get("sub_tasks", [])
            with st.expander(
                f"[{task.get('status','?').upper()}] {task.get('description','')[:80]}…  "
                f"· {task.get('task_id','')}",
                expanded=task.get("status") in ("running", "failed"),
            ):
                col_a, col_b = st.columns([1, 3])
                with col_a:
                    st.markdown(
                        f'<div style="font-size:.72rem;font-weight:700;letter-spacing:.06em;'
                        f'text-transform:uppercase;color:{status_color}">'
                        f'{task.get("status","?").upper()}</div>'
                        f'<div style="font-size:.75rem;color:{GREY_MUTED};margin-top:.2rem">'
                        f'ID: <code>{task.get("task_id","")}</code></div>'
                        f'<div style="font-size:.75rem;color:{GREY_MUTED}">'
                        f'Created: {task.get("created_at","")[:19]}</div>'
                        f'<div style="font-size:.75rem;color:{GREY_MUTED}">'
                        f'Sub-calls: {len(sub_tasks)}</div>',
                        unsafe_allow_html=True
                    )
                with col_b:
                    if task.get("result"):
                        st.markdown(task["result"][:2000])
                    elif task.get("error"):
                        st.error(task["error"])
                    else:
                        st.markdown(
                            f'<div style="color:{GREY_MUTED};font-size:.85rem;font-style:italic">'
                            f'Task is {task.get("status","pending")}…</div>',
                            unsafe_allow_html=True
                        )

                if sub_tasks:
                    with st.expander(f"Sub-agent calls ({len(sub_tasks)})", expanded=False):
                        for i, st_item in enumerate(sub_tasks):
                            st.markdown(
                                f'**{i+1}. {st_item.get("tool","")}**  \n'
                                f'Input: `{json.dumps(st_item.get("input",{}))[:120]}`  \n'
                                f'Result: {str(st_item.get("result",""))[:200]}'
                            )

# ═══════════════════════════════════════════════════════════════════════
# TAB 12 — REPORT MIGRATION
# ═══════════════════════════════════════════════════════════════════════
with tab_migration:
    from nexus.ui.migration_tab import render as _render_migration
    _render_migration(ORANGE, GREY_MUTED, GREY_LINE, WHITE, NEAR_BLACK)

# ═══════════════════════════════════════════════════════════════════════
# TAB 13 — BUSINESS KPIs (BSL)
# ═══════════════════════════════════════════════════════════════════════
with tab_bsl:
    from nexus.ui.bsl_tab import render as _render_bsl
    _render_bsl(st.session_state.get("connected", False))

# ═══════════════════════════════════════════════════════════════════════
# TAB 14 — GAP ANALYSIS & ROADMAP
# ═══════════════════════════════════════════════════════════════════════
with tab_gap:
    from nexus.ui.gap_roadmap_tab import render as _render_gap
    _render_gap(ORANGE, GREY_MUTED, GREY_LINE, WHITE, NEAR_BLACK)
