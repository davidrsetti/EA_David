"""
agents/orchestrator.py — Multi-agent task orchestrator using Claude tool_use.

The orchestrator accepts a high-level task, uses Claude to decompose it into
sub-agent calls (query, APM, impact, diagram, SA advisor, finding assertion),
executes them, and synthesises a final report.

Task state is kept in-memory (dict keyed by task_id).
For persistence across restarts, swap _TASKS for a SQLite-backed store.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── In-memory task store (replace with SQLite for persistence) ──────────
_TASKS: dict[str, dict] = {}


@dataclass
class OrchestratorTask:
    task_id:     str
    user_id:     str
    user_role:   str
    description: str
    created_at:  str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status:      str = "pending"   # pending | running | completed | failed
    result:      str = ""
    sub_tasks:   list[dict] = field(default_factory=list)
    error:       str = ""


# ── Sub-agent tool definitions for the orchestrator Claude instance ─────

_ORCHESTRATOR_TOOLS = [
    {
        "name": "run_kg_query",
        "description": "Ask a natural language question about the enterprise architecture knowledge graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Natural language question."},
            },
            "required": ["question"],
        },
    },
    {
        "name": "run_apm_analysis",
        "description": "Run the Gartner TIME model portfolio analysis for a domain or the whole portfolio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_domain": {"type": "string", "description": "Optional domain filter."},
            },
        },
    },
    {
        "name": "run_impact_analysis",
        "description": "Compute the change impact blast radius for an application or capability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity":      {"type": "string", "description": "Entity name or URI."},
                "change_type": {"type": "string", "description": "E.g. Decommission, Re-platform."},
            },
            "required": ["entity"],
        },
    },
    {
        "name": "run_sa_advisor",
        "description": "Get solutions architecture health report and recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_domain": {"type": "string"},
            },
        },
    },
    {
        "name": "generate_diagram",
        "description": "Generate an architecture diagram from the knowledge graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "diagram_type": {"type": "string",
                    "enum": ["dependency","capability_map","data_lineage",
                             "agent_ecosystem","c4_context","org_ownership","integration"]},
                "entity": {"type": "string"},
                "fmt":    {"type": "string", "enum": ["dot","mermaid"]},
            },
            "required": ["diagram_type"],
        },
    },
    {
        "name": "assert_finding",
        "description": "Record an architectural finding or risk to the knowledge graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label":       {"type": "string"},
                "severity":    {"type": "string", "enum": ["Low","Medium","High","Critical"]},
                "asset_uri":   {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["label", "severity", "asset_uri", "description"],
        },
    },
]

_ORCHESTRATOR_SYSTEM = """You are NEXUS Orchestrator, an autonomous enterprise architecture agent.

You receive high-level tasks and decompose them using the available tools:
- run_kg_query: query the knowledge graph with NL questions
- run_apm_analysis: Gartner TIME portfolio scoring
- run_impact_analysis: change impact blast radius (6 rings)
- run_sa_advisor: architecture health + recommendations
- generate_diagram: architecture diagrams
- assert_finding: write architectural findings to the graph

Approach:
1. Understand what the task is asking for
2. Use 2-6 tool calls to gather the needed information
3. Synthesise a comprehensive executive-quality report

Be thorough but concise. Prioritise findings by business impact.
When you have enough information, write the final report as your end_turn response."""


def _dispatch_orchestrator_tool(name: str, inp: dict, user_role: str) -> str:
    """Execute an orchestrator sub-agent tool call."""
    try:
        if name == "run_kg_query":
            from nexus.agents.guard       import check_intent, build_security_filter
            from nexus.core.nl_to_sparql  import nl_to_sparql
            from nexus.core.stardog_client import get_stardog
            from nexus.core.answer_engine  import synthesise_full
            from nexus.audit.pii_scanner   import scan_and_redact

            q     = inp.get("question", "")
            guard = check_intent(q, user_role)
            if not guard.allowed:
                return f"Blocked: {guard.reason}"
            sec    = build_security_filter(user_role)
            sparql = nl_to_sparql(q, extra_filters=sec.sparql_data_filter)
            db     = get_stardog()
            _, rows = db.to_rows(db.query(sparql))
            scan   = scan_and_redact(rows, redact=True)
            res    = synthesise_full(q, [], scan.redacted_rows, sparql, len(rows), user_role=user_role)
            return res.answer[:2000]

        elif name == "run_apm_analysis":
            from nexus.core.apm_agent import run_apm_agent
            r = run_apm_agent(focus_domain=inp.get("focus_domain", ""), user_role=user_role)
            return (
                f"Health: {r.portfolio_health}/100 | "
                f"TIME: {json.dumps(r.time_summary)} | "
                f"{r.executive_summary[:500]}"
            )

        elif name == "run_impact_analysis":
            from nexus.core.impact_analyzer import analyze_change_impact
            r = analyze_change_impact(
                entity=inp.get("entity", ""),
                change_type=inp.get("change_type", "Decommission"),
                user_role=user_role,
            )
            rings = " | ".join(f"{rg.label}:{rg.count}" for rg in r.rings)
            return f"Risk: {r.risk_level} | Rings: {rings} | {r.narrative[:500]}"

        elif name == "run_sa_advisor":
            from nexus.core.sa_advisor import run_sa_advisor
            r = run_sa_advisor(focus_domain=inp.get("focus_domain", ""), user_role=user_role)
            recs = "; ".join(f"{x.title}" for x in r.recommendations[:5])
            return f"Health: {r.architecture_health_score} | Recs: {recs}"

        elif name == "generate_diagram":
            from nexus.core.artifact_creator import generate_diagram
            r = generate_diagram(
                diagram_type  = inp.get("diagram_type", "dependency"),
                entity        = inp.get("entity", ""),
                depth         = 2,
                fmt           = inp.get("fmt", "mermaid"),
                domain_filter = "",
                max_nodes     = 40,
            )
            return f"Diagram '{r.title}' ({r.node_count} nodes):\n{r.content[:1500]}"

        elif name == "assert_finding":
            from nexus.agents.findings import Finding, assert_finding
            finding = Finding(
                agent_id    = "nexus-orchestrator",
                label       = inp.get("label", ""),
                severity    = inp.get("severity", "Medium"),
                asset_uri   = inp.get("asset_uri", ""),
                description = inp.get("description", ""),
            )
            uri = assert_finding(finding)
            return f"Finding asserted: {uri}"

        else:
            return f"Unknown tool: {name}"

    except Exception as exc:
        logger.error("orchestrator tool '%s' error: %s", name, exc)
        return f"Tool error ({name}): {exc}"


def run_task(task: OrchestratorTask) -> str:
    """
    Execute an orchestrated task using Claude as the planning brain.
    Updates task.status and task.result in-place.
    Returns the final report string.
    """
    from nexus.core.claude_client import get_claude
    from nexus.config.settings    import settings

    task.status = "running"
    _TASKS[task.task_id] = task.__dict__

    client   = get_claude()
    messages = [{"role": "user", "content": task.description}]
    report   = ""

    for _ in range(10):
        try:
            response = client.messages.create(
                model      = settings.anthropic.agent_model,
                max_tokens = 4096,
                system     = [{"type": "text", "text": _ORCHESTRATOR_SYSTEM}],
                tools      = _ORCHESTRATOR_TOOLS,
                messages   = messages,
            )
        except Exception as exc:
            task.status = "failed"
            task.error  = str(exc)
            _TASKS[task.task_id] = task.__dict__
            return f"Orchestrator error: {exc}"

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    report += block.text
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result_str = _dispatch_orchestrator_tool(block.name, block.input, task.user_role)
                task.sub_tasks.append({
                    "tool":   block.name,
                    "input":  block.input,
                    "result": result_str[:300],
                })
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     result_str,
                })
            messages.append({"role": "user", "content": tool_results})

    task.status = "completed" if report else "failed"
    task.result = report
    _TASKS[task.task_id] = task.__dict__
    return report


def submit_task(description: str, user_id: str, user_role: str) -> str:
    """Submit a task for async execution. Returns task_id."""
    task = OrchestratorTask(
        task_id     = f"task_{uuid.uuid4().hex[:12]}",
        user_id     = user_id,
        user_role   = user_role,
        description = description,
    )
    _TASKS[task.task_id] = task.__dict__

    import threading
    t = threading.Thread(target=run_task, args=(task,), daemon=True)
    t.start()
    return task.task_id


def get_task(task_id: str) -> dict | None:
    return _TASKS.get(task_id)


def list_tasks(user_id: str = "", limit: int = 20) -> list[dict]:
    tasks = list(_TASKS.values())
    if user_id:
        tasks = [t for t in tasks if t.get("user_id") == user_id]
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return tasks[:limit]
