"""
core/tool_executor.py — Dispatches Claude tool_use calls to NEXUS functions.

Called by claude_client.tool_call_loop() when Claude requests a tool.
Each tool returns a string result that Claude sees as tool_result content.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_MAX_SPARQL_ROWS = 50   # cap rows returned to Claude per tool call


def dispatch(
    tool_name: str,
    tool_input: dict,
    user_role: str = "analyst",
    session_id: str = "",
) -> str:
    """
    Execute the named tool and return a result string for Claude.
    Errors are returned as strings (not raised) so Claude can reason about them.
    """
    try:
        if tool_name == "run_sparql":
            return _run_sparql(tool_input, user_role)
        elif tool_name == "get_entity_context":
            return _get_entity_context(tool_input)
        elif tool_name == "assert_finding":
            return _assert_finding(tool_input, user_role)
        elif tool_name == "search_ontology":
            return _search_ontology(tool_input)
        elif tool_name == "query_databricks":
            return _query_databricks(tool_input, user_role)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as exc:
        logger.error("dispatch('%s') unhandled error: %s", tool_name, exc)
        return f"Tool error ({tool_name}): {exc}"


# ── Tool implementations ────────────────────────────────────────────────


def _run_sparql(inp: dict, user_role: str) -> str:
    from nexus.core.stardog_client import get_stardog
    from nexus.core.nl_to_sparql  import _inject_missing_prefixes

    sparql = inp.get("sparql", "").strip()
    if not sparql:
        return "Error: no SPARQL provided."

    sparql = _inject_missing_prefixes(sparql)
    db     = get_stardog()

    complexity = db.estimate_complexity(sparql)
    if complexity > 30:
        return f"Query too complex (score {complexity}). Simplify and retry."

    try:
        raw = db.query(sparql)
        cols, rows = db.to_rows(raw)
    except Exception as exc:
        return f"SPARQL execution error: {exc}"

    if not rows:
        return "Query executed successfully. No results returned."

    rows = rows[:_MAX_SPARQL_ROWS]
    return json.dumps({"columns": cols, "rows": rows, "total": len(rows)}, default=str)


def _get_entity_context(inp: dict) -> str:
    from nexus.agents.context_provider import get_context

    entity_name = inp.get("entity_name", "").strip()
    if not entity_name:
        return "Error: entity_name is required."

    try:
        bundle = get_context(entity_name, requesting_agent="claude-answer-engine")
        return json.dumps(bundle.to_dict(), default=str)
    except Exception as exc:
        return f"Context retrieval error: {exc}"


def _assert_finding(inp: dict, user_role: str) -> str:
    if user_role not in ("admin", "data-steward", "agent", "agent-admin"):
        return "Permission denied: finding assertion requires data-steward or admin role."

    from nexus.agents.findings import Finding, assert_finding

    label       = inp.get("label", "")
    severity    = inp.get("severity", "Medium")
    asset_uri   = inp.get("asset_uri", "")
    description = inp.get("description", "")

    if not all([label, asset_uri, description]):
        return "Error: label, asset_uri, and description are all required."

    finding = Finding(
        agent_id    = "claude-answer-engine",
        label       = label,
        severity    = severity,
        asset_uri   = asset_uri,
        description = description,
    )
    try:
        uri = assert_finding(finding)
        return f"Finding asserted: {uri}"
    except Exception as exc:
        return f"Finding assertion failed: {exc}"


def _search_ontology(inp: dict) -> str:
    from nexus.core.ontology import get_ontology

    term = inp.get("term", "").strip().lower()
    if not term:
        return "Error: term is required."

    ont   = get_ontology()
    lines = ont.full_text.splitlines()
    hits  = [l for l in lines if term in l.lower()][:30]

    if not hits:
        return f"No ontology entries found containing '{term}'."
    return "\n".join(hits)


def _query_databricks(inp: dict, user_role: str) -> str:
    _ALLOWED_ROLES = {"analyst", "admin", "data-steward"}
    if user_role not in _ALLOWED_ROLES:
        return f"Permission denied: role '{user_role}' cannot execute Databricks queries."

    sql = inp.get("sql", "").strip()
    if not sql:
        return "Error: sql is required."
    if not sql.upper().lstrip().startswith("SELECT"):
        return "Error: only SELECT queries are permitted."

    try:
        from nexus.core.databricks_client import get_databricks
        cols, rows = get_databricks().query(sql)
        return json.dumps({"columns": cols, "rows": rows[:20]}, default=str)
    except Exception as exc:
        return f"Databricks query failed: {exc}"
