# CLAUDE.md — NEXUS v2 Enterprise Knowledge Graph Platform

This file provides comprehensive guidance to Claude Code when working with the EA_David codebase.

## Project Identity

**NEXUS v2** is an Enterprise Knowledge Graph (EKG) platform providing:
- Conversational AI over a Stardog RDF/OWL enterprise architecture graph
- Solution Architecture advisory (guided interview + pattern matching + recommendations)
- Application Portfolio Management (Gartner TIME model scoring)
- Architecture Diagram generation (7 types, DOT/Mermaid/draw.io)
- Change Impact Radar (6-ring blast radius analysis)
- AI Agent Governance (risk scoring + compliance registry)
- Business Semantic Layer (glossary, KPIs, business rules — in progress)
- **GiGi/Glean Integration** via MCP server — allows the enterprise ChatBot to query NEXUS as a tool

**Stack:** Python 3.11+, FastAPI (port 8000), Streamlit (port 8501), StarDog 8+ (SPARQL), OpenAI (o3-mini + gpt-4o + gpt-4o-mini), Anthropic Claude (claude-sonnet-4-6), Databricks Unity Catalog

---

## Repository Layout

```
EA_David/                              ← git root
├── EA_David/                          ← Python package root (import as "nexus.*")
│   ├── agents/                        ← Agent layer (guard, clarifier, registry, findings, session, orchestrator)
│   │   ├── guard.py                   ← Two-layer safety: LLM intent check + SPARQL FILTER injection
│   │   ├── clarifier.py               ← Intent mapping → ClarificationPlan (HitL pre-flight)
│   │   ├── registry.py                ← AI agent catalogue lookup
│   │   ├── findings.py                ← AgentFinding write-back to graph
│   │   ├── session.py                 ← Multi-turn conversation state (stored in graph)
│   │   ├── context_provider.py        ← Entity context bundle (2-hop neighbourhood + policies + findings)
│   │   ├── orchestrator.py            ← [PLANNED] Multi-agent orchestration via Claude tool_use
│   │   └── background_runner.py       ← [PLANNED] Autonomous scheduled agents (APScheduler)
│   ├── api/
│   │   ├── main.py                    ← 21+ FastAPI endpoints (see Endpoints section)
│   │   ├── auth.py                    ← JWT validation + role extraction
│   │   └── middleware.py              ← Rate limiting, CORS
│   ├── audit/
│   │   ├── logger.py                  ← Immutable JSON-L audit log (file/Postgres/Azure Monitor sinks)
│   │   └── pii_scanner.py             ← Regex PII detection + redaction (8 patterns)
│   ├── config/
│   │   ├── settings.py                ← Singleton config. All env vars flow through Settings() — never os.getenv() elsewhere
│   │   └── ontology_prefixes.py       ← 40+ RDF PREFIX declarations, SPARQL_PREFIX_BLOCK, DOMAIN_HINTS
│   ├── core/
│   │   ├── nl_to_sparql.py            ← NL→SPARQL translation (o3-mini + ontology snapshot injection)
│   │   ├── nl_to_sql.py               ← NL→SQL for Databricks (keyword-blocked, BU/Domain scoped)
│   │   ├── answer_engine.py           ← Result synthesis (gpt-4o → migrating to claude-sonnet-4-6 with tool_use)
│   │   ├── clarifier.py               ← Duplicate of agents/clarifier (consolidation needed)
│   │   ├── ontology.py                ← Live ontology snapshot from Stardog (1-hour TTL, thread-safe cache)
│   │   ├── stardog_client.py          ← Singleton HTTP SPARQL client + complexity heuristic
│   │   ├── databricks_client.py       ← Singleton Databricks SQL connector
│   │   ├── sa_advisor.py              ← Portfolio health: 6 parallel SPARQL queries + LLM synthesis
│   │   ├── sa_advisor_v2.py           ← Guided SA interview (ontology-driven, resolves classes at runtime)
│   │   ├── apm_agent.py               ← Gartner TIME model scoring (4 dimensions, 0–10 each)
│   │   ├── impact_analyzer.py         ← Change Impact Radar: 6 parallel SPARQL traversals
│   │   ├── artifact_creator.py        ← 7 diagram types via @diagram_type() decorator registry
│   │   ├── ai_governance.py           ← AI agent risk scoring + compliance rules
│   │   ├── claude_client.py           ← [PLANNED] Anthropic singleton with tool_call_loop() + streaming
│   │   ├── tool_executor.py           ← [PLANNED] Maps Claude tool_use → NEXUS functions
│   │   ├── bsl_engine.py              ← [PLANNED] Business Semantic Layer: glossary, KPIs, rules
│   │   ├── gap_analyzer.py            ← [PLANNED] AS-IS vs TO-BE gap analysis
│   │   ├── roadmap_generator.py       ← [PLANNED] Architecture roadmap generation (Gantt-ready)
│   │   ├── scenario_engine.py         ← [PLANNED] "What-if" scenario modeling
│   │   ├── sparql_feedback.py         ← [PLANNED] SPARQL correction feedback loop (few-shot examples)
│   │   ├── kg_populator.py            ← [PLANNED] AI-assisted bulk import (CSV/JSON → SPARQL INSERT)
│   │   ├── kg_validator.py            ← [PLANNED] Triple validation against ontology constraints
│   │   ├── vector_store.py            ← [PLANNED] pgvector semantic search (fallback for zero-result SPARQL)
│   │   └── cache.py                   ← [PLANNED] Redis decorator-based caching
│   ├── ui/
│   │   ├── app.py                     ← Main Streamlit app (tab host + Knowledge Graph Chat + sidebar)
│   │   ├── guided_sa_tab.py           ← 4-step SA interview UI
│   │   ├── data_query_tab.py          ← NL→SQL over Databricks/Unity Catalog
│   │   ├── diagram_tab.py             ← Architecture Diagram Studio (7 types)
│   │   ├── portfolio_tab.py           ← Portfolio Intelligence (TIME quadrant + health score)
│   │   ├── sa_health_tab.py           ← SA Health (6-query assessment dashboard)
│   │   ├── impact_tab.py              ← Change Impact Radar (6-ring blast radius)
│   │   ├── audit_tab.py               ← Audit log viewer (filters, metrics, export)
│   │   ├── ai_governance_tab.py       ← AI Agent Governance Console
│   │   ├── bsl_tab.py                 ← [PLANNED] Business Semantic Layer (glossary, KPIs)
│   │   ├── gap_analysis_tab.py        ← [PLANNED] Gap Analysis (AS-IS vs TO-BE heat map)
│   │   ├── roadmap_tab.py             ← [PLANNED] Roadmap Planner (Plotly Gantt)
│   │   ├── kg_population_tab.py       ← [PLANNED] KG Population assistant
│   │   └── agent_tasks_tab.py         ← [PLANNED] Background agent task monitor
│   ├── mcp_server.py                  ← [PLANNED] MCP server for GiGi/Glean + Claude Code integration
│   ├── sparql_corrections.py          ← Corrected SPARQL reference (v8→v2.1 ontology migration)
│   ├── validation_app.py              ← Standalone 9-stage pipeline tester (Streamlit)
│   ├── uc_to_stardog.py               ← Databricks Unity Catalog → StarDog loader
│   └── requirements.txt
├── ea-ontology-consolidated-10.ttl    ← Source-of-truth ontology (88KB, 40+ namespaces)
├── logs/
├── tests/
│   ├── smoke_test.py                  ← 31 competency questions across 7 categories
│   └── unit/                          ← Unit tests: apm_scoring, injection_guard, pii_scanner, sparql_utils
├── ALIGNMENT_GUIDE.md                 ← Ontology v8→v2.1 migration guide
└── README.md
```

---

## Running the Application

```bash
# From EA_David/EA_David/

# API (port 8000)
python -m uvicorn nexus.api.main:app --reload --port 8000 --host 0.0.0.0

# UI (port 8501)
python -m streamlit run nexus/ui/app.py --server.port 8501

# MCP Server (stdio — for GiGi/Glean or Claude Code integration)
python -m nexus.mcp_server

# Standalone pipeline tester
python -m streamlit run validation_app.py

# Generate JWT for API testing
python -c "from nexus.api.auth import create_token; print(create_token('alice', 'analyst'))"

# Run tests
python tests/smoke_test.py
python -m pytest tests/unit/
```

---

## Configuration (.env)

All configuration flows through `config/settings.py::Settings()`. **Never call `os.getenv()` outside this file.**

```bash
# StarDog
STARDOG_ENDPOINT=http://localhost:5820/nexus/query
STARDOG_TOKEN=<bearer-token>
STARDOG_DB=nexus
STARDOG_VERIFY_TLS=false              # self-signed Kubernetes cert
STARDOG_TIMEOUT=30

# OpenAI
OPENAI_API_KEY=<key>
SPARQL_MODEL=o3-mini                  # reasoning model for SPARQL generation
CLARIFY_MODEL=gpt-4o-mini             # intent classification
ANSWER_MODEL=gpt-4o                   # synthesis (migrating → claude-sonnet-4-6)
GUARD_MODEL=gpt-4o-mini               # safety guard
LLM_MAX_TOKENS=2000

# Anthropic (new — for claude-sonnet-4-6 answer engine + MCP)
ANTHROPIC_API_KEY=<key>
CLAUDE_ANSWER_MODEL=claude-sonnet-4-6
CLAUDE_AGENT_MODEL=claude-sonnet-4-6
CLAUDE_CACHE=true                     # enable prompt caching on ontology snapshot

# Security
JWT_SECRET=<random-secret>            # randomised per-process in dev if unset
TOKEN_EXPIRE_MINS=480
RATE_LIMIT_PER_HOUR=60
MAX_RESULT_ROWS=500
MAX_SPARQL_COMPLEXITY=25

# Audit
AUDIT_SINK=file                       # file | postgres | azure_monitor
AUDIT_LOG_PATH=logs/nexus_audit.jsonl
AUDIT_ENABLED=true

# Databricks
DATABRICKS_HOST=<host>
DATABRICKS_HTTP_PATH=<path>
DATABRICKS_TOKEN=<token>

# Optional integrations
REDIS_URL=redis://localhost:6379      # for response caching (Phase 5)
VECTOR_PG_URL=postgresql://...        # for pgvector semantic search (Phase 5)
SNOW_INSTANCE=<instance>             # ServiceNow (Phase 4, optional)
```

---

## Query Pipeline (9 Stages)

Every natural language question flows through these stages in sequence:

```
User Question
  ↓ 1. GUARD (agents/guard.py)
       LLM intent classification (gpt-4o-mini)
       Risk: LOW | MEDIUM | HIGH | BLOCKED
       BLOCKS: credential exfiltration, mass PII dump, privilege escalation
  ↓ 2. CLARIFIER (agents/clarifier.py)
       Maps question → ontology domains/entities → ClarificationPlan
       May pause for human-in-the-loop clarification if ambiguous
  ↓ 3. SECURITY FILTER (guard.py → build_security_filter())
       Injects SPARQL FILTER clauses based on JWT role + department
       Role clearances: admin/data-steward (all), analyst (Public/Internal), viewer (Public + own dept)
  ↓ 4. NL→SPARQL (core/nl_to_sparql.py)
       Model: o3-mini (reasoning). Fallback: gpt-4o
       Input: question + clarification + role + extra FILTER + live ontology snapshot
       Output: clean SPARQL SELECT
  ↓ 5. COMPLEXITY CHECK (stardog_client.py → estimate_complexity())
       Score: +1 triple, +2 OPTIONAL, +3 UNION, +4 SERVICE, +3 nested SELECT, +1 FILTER
       Rejects if score > MAX_SPARQL_COMPLEXITY (default: 25)
  ↓ 6. EXECUTE (core/stardog_client.py)
       HTTP POST to StarDog SPARQL endpoint
       Retry on SSL EOF (Zscaler-compatible)
  ↓ 7. PII SCAN (audit/pii_scanner.py)
       8 regex patterns: email, phone, UK NINO, US SSN, credit card, IP, passport, IBAN
       Redacts by default before returning results
  ↓ 8. SYNTHESISE (core/answer_engine.py)
       Current: gpt-4o → single-shot synthesis
       Planned: claude-sonnet-4-6 with tool_use loop (3–5 graph traversals per question)
       Output: Direct Answer / Reasoning & Explanation / Confidence & Caveats
  ↓ 9. AUDIT LOG (audit/logger.py)
       Immutable JSON-L: event_id, timestamp, user_id, risk_level, pii_detected, latency_ms
       Sinks: file (default) | Postgres | Azure Monitor
  ↓ Response
```

---

## UI Tabs (All 9 Current + 5 Planned)

| Tab | Emoji | File | Status | Purpose |
|-----|-------|------|--------|---------|
| Knowledge Graph Chat | 💬 | `app.py` | Live | NL query → 9-stage pipeline, SPARQL inspector, multi-turn |
| Guided SA Advisor | 🧭 | `guided_sa_tab.py` | Live | 4-step interview → graph-grounded SA recommendation |
| Freeform SA Diagram | 🏛 | `app.py` | Live | ArchiMate 3.1 generation via Claude API, draw.io export |
| Data Query | 📊 | `data_query_tab.py` | Live | NL→SQL over Databricks Unity Catalog, BU/Domain governance |
| Portfolio Intelligence | 📊 | `portfolio_tab.py` | Live | Gartner TIME quadrant + health score (auto-scored) |
| SA Health | 🏥 | `sa_health_tab.py` | Live | 6-query architecture health: gaps, debt, orphans, hotspots |
| Architecture Diagrams | 🗺️ | `diagram_tab.py` | Live | 7 diagram types (DOT/Mermaid), depth/node control, draw.io |
| Change Impact | 💥 | `impact_tab.py` | Live | 6-ring blast radius: dependents, capabilities, data, agents, people |
| Audit | 🔍 | `audit_tab.py` | Live | JSONL log viewer, metrics, date/role/risk filters |
| AI Governance | ⚙️ | `ai_governance_tab.py` | Live | AI agent risk registry + compliance scoring |
| Business Semantic Layer | 📚 | `bsl_tab.py` | Planned | Glossary, KPIs, business rules linked to ontology |
| Gap Analysis | 🎯 | `gap_analysis_tab.py` | Planned | AS-IS vs TO-BE heat map, capability gap detection |
| Roadmap Planner | 🗓️ | `roadmap_tab.py` | Planned | Plotly Gantt chart, scenario comparison |
| KG Population | 📥 | `kg_population_tab.py` | Planned | AI-assisted bulk import, triple validation |
| Agent Tasks | 🤖 | `agent_tasks_tab.py` | Planned | Background autonomous agent task monitor |

Brand colours: `#F36633` (orange primary), dark theme.

---

## FastAPI Endpoints (api/main.py)

Port 8000. All require `Authorization: Bearer <JWT>`. Auto-docs at `http://localhost:8000/docs`.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/query` | POST | Main NL query pipeline |
| `/v1/query/stream` | POST | [Planned] SSE streaming variant |
| `/v1/context` | POST | Entity context bundle |
| `/v1/assert` | POST | Agent writes finding to graph |
| `/v1/session` | POST | Create/update conversation session |
| `/v1/lineage/{asset}` | GET | Data lineage traversal |
| `/v1/agent/{id}` | GET | Agent profile + tools |
| `/v1/sa-advisor` | POST | Full SA Advisor report |
| `/v1/sa-advisor/ask` | POST | Ad-hoc SA question |
| `/v1/apm/analyze` | POST | Portfolio TIME model analysis |
| `/v1/apm/application/{id}` | GET | Single app TIME score |
| `/v1/artifact/diagram` | POST | Architecture diagram (DOT/Mermaid) |
| `/v1/impact/analyze` | POST | Change Impact Radar |
| `/v1/adr/create` | POST | Generate + store ADR |
| `/v1/adr/list` | GET | List ADRs |
| `/v1/ai-governance` | GET | AI governance score + agent registry |
| `/v1/health/graph` | GET | Graph health (Kubernetes probe) |
| `/v1/agent/task` | POST | [Planned] Submit autonomous agent task |
| `/v1/agent/task/{id}` | GET | [Planned] Poll task result |
| `/v1/bsl/terms` | GET/POST | [Planned] Business glossary |
| `/v1/bsl/kpis` | GET/POST | [Planned] KPI definitions |
| `/v1/gap-analysis` | POST | [Planned] AS-IS vs TO-BE gap analysis |
| `/v1/roadmap/generate` | POST | [Planned] Architecture roadmap |
| `/v1/scenario/model` | POST | [Planned] What-if scenario |
| `/v1/kg/import` | POST | [Planned] Bulk KG population |
| `/v1/sparql/correct` | POST | [Planned] SPARQL correction feedback |
| `/v1/search/semantic` | GET | [Planned] Vector semantic search |
| `/v1/annotations` | GET/POST | [Planned] Collaborative annotations |

---

## Ontology Namespaces (config/ontology_prefixes.py)

Source of truth: `ea-ontology-consolidated-10.ttl` (88KB)

| Prefix | URI | Domain |
|--------|-----|--------|
| `ea` | `https://ontology.ea.example.org/ea#` | Core EA: capabilities (L1/L2/L3), technology domains, patterns |
| `app` | `https://ontology.ea.example.org/app#` | Applications: lifecycle, owner, dependsOn, enablesCapability |
| `hr` | `https://ontology.ea.example.org/hr#` | People, departments, certifications |
| `id` | `https://ontology.ea.example.org/id#` | Identity: roles, groups, service principals |
| `data` | `https://ontology.ea.example.org/data#` | DataProduct, Dataset, lineage, classification, PII flag |
| `ai` | `https://ontology.ea.example.org/ai#` | AI agents, risk tier, tools, model family |
| `sec` | `https://ontology.ea.example.org/security#` | Policies, access rights, classification levels |
| `infra` | `https://ontology.ea.example.org/infra#` | Compute, storage, container clusters |
| `net` | `https://ontology.ea.example.org/net#` | Networks, subnets, private endpoints |
| `fw` | `https://ontology.ea.example.org/fw#` | Firewall policies and rules |
| `int` | `https://ontology.ea.example.org/int#` | Integrations (first-class objects, not just app:dependsOn) |
| `sol` | `https://ontology.ea.example.org/sol#` | Solutions, TIME disposition (Tolerate/Invest/Migrate/Eliminate) |
| `adv` | `https://ontology.ea.example.org/adv#` | Architecture decisions, options, roadmap items |
| `art` | `https://ontology.ea.example.org/artifact#` | EA artifacts: diagrams, ADRs |
| `gov` | `https://ontology.ea.example.org/gov#` | Governance: regulations, contracts, SLAs, change requests |
| `cost` | `https://ontology.ea.example.org/cost#` | Cost models, licence costs |
| `arch` | `https://ontology.ea.example.org/arch#` | Reference architectures, TOGAF phases |
| `ops` / `nexus` | `https://nexus.platform/ops#` | Platform ops: AgentFinding, ConversationSession, AgentTask |
| `bsl` | `https://ontology.ea.example.org/bsl#` | [Planned] Business glossary terms |
| `kpi` | `https://ontology.ea.example.org/kpi#` | [Planned] KPIs and metrics |
| `rule` | `https://ontology.ea.example.org/rule#` | [Planned] Business rules |

Key entity classes by domain (use in SPARQL):
- **Applications:** `app:Application` — `app:lifecycle`, `app:techOwner`, `app:dependsOn`, `ea:enablesBusinessCapability`
- **Capabilities:** `ea:BusinessCapabilityL1/L2/L3`, `ea:TechnologyCapabilityL1/L2/L3`, `ea:CSOCapabilityL1/L2/L3`
- **People:** `hr:User` — `hr:fullName`, `hr:mail`, `hr:memberOfDepartment`
- **Data:** `data:DataProduct` — `data:classification`, `data:dataOwner`, `data:lineageFrom`, `data:containsPII`
- **AI Agents:** `ai:Agent` — `ai:riskTier`, `ai:agentPlatform`, `ai:hasTool`, `ai:agentReads`, `ai:agentWrites`
- **Findings:** `ops:AgentFinding` — `ops:severity`, `ops:foundBy`, `ops:affects`, `ops:findingStatus`
- **Sessions:** `ops:ConversationSession` — `ops:sessionUserId`, `ops:lastIntent`, `ops:entityFocus`

---

## LLM Model Assignments

| Task | Model | Why |
|------|-------|-----|
| SPARQL generation | `o3-mini` (reasoning) | Structured code generation; fallback to gpt-4o |
| Intent classification / guard | `gpt-4o-mini` | Low-cost, fast, binary classification |
| Answer synthesis (current) | `gpt-4o` | Best prose quality |
| Answer synthesis (target) | `claude-sonnet-4-6` + tool_use | Multi-hop graph reasoning loop (3–5 traversals) |
| SA Advisor / APM narrative | `gpt-4o` / `claude-sonnet-4-6` | Long-form structured recommendations |
| Freeform diagram generation | `claude-sonnet-4-6` | ArchiMate/draw.io XML generation |

**Critical:** Reasoning models (`o3`, `o1` families) use `max_completion_tokens` not `max_tokens`. The `_token_param()` helper in each module handles this automatically. Never use `max_tokens` with o3-mini.

---

## SPARQL Conventions

1. **Technology filtering:** Always filter on **capability labels**, not technology labels.
   - Correct: `FILTER(CONTAINS(LCASE(?capLabel), "container"))` where `?cap` is a `ea:TechnologyCapabilityL3`
   - Wrong: `FILTER(CONTAINS(LCASE(?techLabel), "container"))` where `?tech` is `ea:Technology`

2. **Variable scoping:** Never reuse a variable name in inner and outer queries.
   ```sparql
   # Bad: ?app used in both scopes
   SELECT ?app WHERE { { SELECT ?app WHERE { ?app a app:Application } } ?app ... }
   
   # Good: ?innerApp scoped to subquery
   SELECT ?app WHERE { { SELECT ?innerApp WHERE { ?innerApp a app:Application } } ?app ... }
   ```

3. **Always declare every PREFIX** that appears in the query. The PREFIX block is auto-injected by `nl_to_sparql.py` but explicit is safer.

4. **Nullable properties:** Use `OPTIONAL { }` for techOwner, lifecycle, businessOwner — these are often missing.

5. **Complexity limit:** Default MAX_SPARQL_COMPLEXITY = 25. Score: +1 triple, +2 OPTIONAL, +3 UNION, +4 SERVICE, +3 SUBQUERY, +1 FILTER.

6. **Case-insensitive filtering:** `FILTER(CONTAINS(LCASE(?label), "term"))` — always lowercase both sides.

---

## Security Architecture

| Layer | Implementation | File |
|-------|---------------|------|
| Intent guard | LLM classifies question intent; BLOCKED if unsafe | `agents/guard.py::check_intent()` |
| Row-level security | SPARQL FILTER clauses injected per role + department | `agents/guard.py::build_security_filter()` |
| SPARQL injection | Rejects `}`, `{`, `#`, `;` in all filter params | `api/main.py::_safe_filter_param()` |
| Complexity cap | Rejects queries with score > MAX_SPARQL_COMPLEXITY | `core/stardog_client.py::estimate_complexity()` |
| PII redaction | 8 regex patterns; redacts before response | `audit/pii_scanner.py` |
| JWT auth | Bearer token, role extraction, 8-hour expiry | `api/auth.py` |
| Rate limiting | 60 requests/hour per user (configurable) | `api/middleware.py` |
| Audit trail | Immutable JSON-L, credential scrubbing | `audit/logger.py` |
| Data classification | Public/Internal/Confidential/Restricted per role | `agents/guard.py` |

---

## Agent Subsystem

| Agent | File | Purpose |
|-------|------|---------|
| Guard | `agents/guard.py` | Two-layer safety: LLM intent + SPARQL FILTER injection |
| Clarifier | `agents/clarifier.py` | Maps question → ontology domains + entities |
| Registry | `agents/registry.py` | AI agent catalogue lookup (profile + tools) |
| Findings | `agents/findings.py` | `assert_finding()` — writes AgentFinding triples to graph |
| Session | `agents/session.py` | Stores turn context in graph; `get_session_context()` for coreference |
| Context Provider | `agents/context_provider.py` | `get_context(entity)` — 2-hop neighbourhood + policies + findings |
| Orchestrator | `agents/orchestrator.py` | [PLANNED] Multi-agent orchestration via Claude tool_use |
| Background Runner | `agents/background_runner.py` | [PLANNED] APScheduler for nightly/weekly autonomous tasks |

**Known issue:** `agents/session.py` writes session state after each turn but `nl_to_sparql.py` and `clarifier.py` never read it. Multi-turn context is stored but not consumed. Fix: thread `session_id` through the pipeline and inject `get_session_context()` result into the SPARQL generation system prompt.

---

## MCP Server (mcp_server.py) — GiGi/Glean Integration

The MCP server exposes NEXUS as a set of tools that **GiGi** (the enterprise ChatBot on Glean) can invoke. This is the primary integration point for enterprise-wide access to the knowledge graph.

```bash
# Run MCP server (stdio transport)
python -m nexus.mcp_server

# Configure in Claude Code (.claude/settings.json):
{
  "mcpServers": {
    "nexus-kg": {
      "command": "python",
      "args": ["-m", "nexus.mcp_server"],
      "env": {"NEXUS_API_URL": "http://localhost:8000", "NEXUS_TOKEN": "..."}
    }
  }
}

# Configure in Glean MCP registry (production):
# Register same server with NEXUS_API_URL pointing to production host
```

MCP tools exposed:
- `nexus_query` — Natural language KG query
- `nexus_impact_analyze` — Change impact blast radius
- `nexus_apm_analyze` — Portfolio TIME scoring
- `nexus_sa_advisor` — SA recommendations
- `nexus_generate_diagram` — Architecture diagram
- `nexus_assert_finding` — Record architectural finding
- `nexus_get_entity` — Full entity context
- `nexus_list_adrs` — List Architecture Decision Records
- `nexus_graph_health` — Graph health metrics

**Add to requirements.txt:** `mcp>=1.0.0`

---

## Enhancement Roadmap (Prioritised)

### Phase 1 — Agentic AI Core (Highest Priority)
1. `core/claude_client.py` — Anthropic SDK singleton with `tool_call_loop()`, streaming, prompt caching on ontology (88KB)
2. `core/tool_executor.py` — Maps Claude tool_use → NEXUS functions (run_sparql, get_entity_context, assert_finding, search_ontology)
3. `core/answer_engine.py` — Migrate from GPT-4o single-shot → Claude tool_use multi-hop reasoning
4. `mcp_server.py` — MCP server for GiGi/Glean + Claude Code integration
5. Fix multi-turn: thread `session_id` through pipeline; inject session context into SPARQL prompt
6. Add SSE streaming endpoint `POST /v1/query/stream`
7. `agents/orchestrator.py` — Multi-agent orchestration (Claude decompose → sub-agent dispatch)
8. `agents/background_runner.py` — APScheduler: nightly portfolio scan, weekly gap report

### Phase 2 — Business Semantic Layer (High Priority)
1. New ontology namespaces: `bsl:` (glossary), `kpi:` (metrics), `rule:` (business rules)
2. Add classes to `ea-ontology-consolidated-10.ttl`: BusinessTerm, KPI, BusinessRule
3. `core/bsl_engine.py` + `ui/bsl_tab.py` + BSL API endpoints

### Phase 3 — EA Tools (High Priority)
1. `core/gap_analyzer.py` — AS-IS vs TO-BE comparison; new ontology: arch:TargetArchitecture, arch:CapabilityGap
2. `core/roadmap_generator.py` — Gantt-ready roadmap from APM + gap analysis
3. `core/scenario_engine.py` — What-if portfolio modeling
4. `core/sparql_feedback.py` — Correction store + few-shot injection into nl_to_sparql()

### Phase 4 — Knowledge Graph Population (Medium Priority)
1. `core/kg_populator.py` — CSV/JSON → SPARQL INSERT with Claude-inferred mappings
2. `core/itsm_client.py` — ServiceNow CMDB sync (optional)

### Phase 5 — Infrastructure (Medium Priority)
1. `core/vector_store.py` — pgvector semantic search (fallback for 0-result SPARQL)
2. `core/cache.py` — Redis caching (SPARQL 5min, APM 15min, context 30min)
3. Async FastAPI: convert all endpoints to `async def` + `asyncio.to_thread()`

---

## Ontology Migration Reference (v8 → v2.1)

See `ALIGNMENT_GUIDE.md` for full mapping. Key changes:

| Old (v8) | New (v2.1) | Note |
|----------|-----------|------|
| `agent:AIAgent` | `ai:Agent` | Namespace + name change |
| `agent:AgentFinding` | `nexus:AgentFinding` | Moved to ops namespace |
| `ea:BusinessCapability` | `ea:BusinessCapabilityL3` | L3 is the queryable leaf level |
| `ea:realisedBy` | `ea:enablesBusinessCapability` | Direction flipped (app→cap, not cap→app) |
| `http://nexus.enterprise.com/` | `https://ontology.ea.example.org/` | Base URI changed |
| `app:dependsOn` | `int:Integration` (objects) | Integrations are now first-class |

When writing SPARQL: consult `sparql_corrections.py` for known-good query patterns, then test with `validation_app.py`.

---

## External Connections

- **StarDog TLS:** `STARDOG_VERIFY_TLS=false` — self-signed Kubernetes cert
- **Databricks SSL:** `_tls_no_verify=True` in `databricks_client.py` — Zscaler corporate SSL interception
- **Zscaler SSL drops:** `stardog_client.py` retries on SSL EOF (3 attempts, exponential backoff)
- Both tokens expire and need periodic refresh in `.env`
- `config/settings.py::_patch_corporate_ssl()` removes stale `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` vars set by Zscaler

---

## Development Conventions

- **Singletons:** `get_stardog()`, `get_databricks()` — expensive connections, cached per process
- **Session state keys:** Prefixed by tab (e.g., `dq_` for Data Query, `sa_` for SA Advisor) to avoid cross-tab collisions
- **Config:** All configuration via `Settings()` — no hardcoded values in core modules
- **Reasoning models:** Use `_token_param()` helper to get `max_completion_tokens` vs `max_tokens` based on model name
- **Ontology cache:** `core/ontology.py::get_ontology()` — thread-safe double-checked locking; returns stub if StarDog unavailable
- **SPARQL prefix injection:** `nl_to_sparql.py` auto-injects missing PREFIX declarations after generation
- **Import path:** The Python package is imported as `nexus.*` (symlink or PYTHONPATH from project root)
