"""
mcp_server.py — NEXUS MCP Server for GiGi/Glean and Claude Code integration.

Run:
    python -m nexus.mcp_server

Configure in Glean MCP registry:
    {
      "name": "nexus-kg",
      "command": "python",
      "args": ["-m", "nexus.mcp_server"],
      "env": {
        "NEXUS_API_URL": "http://<nexus-host>:8000",
        "NEXUS_TOKEN": "<service-account-jwt>"
      }
    }

Configure for Claude Code (.claude/settings.json):
    {
      "mcpServers": {
        "nexus-kg": {
          "command": "python",
          "args": ["-m", "nexus.mcp_server"],
          "env": {
            "NEXUS_API_URL": "http://localhost:8000",
            "NEXUS_TOKEN": "<your-jwt>"
          }
        }
      }
    }

When NEXUS_API_URL is set, the server calls the REST API (works as a separate process).
When unset, it imports Python modules directly (useful for local development).
"""
from __future__ import annotations

import json
import logging
import os
import sys

# Ensure package is importable when run as __main__
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

_API_URL  = os.getenv("NEXUS_API_URL", "").rstrip("/")
_API_TOKEN = os.getenv("NEXUS_TOKEN",  "")


def _api_post(path: str, payload: dict) -> dict:
    """Call NEXUS REST API and return parsed JSON."""
    import httpx
    url     = f"{_API_URL}{path}"
    headers = {"Authorization": f"Bearer {_API_TOKEN}", "Content-Type": "application/json"}
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def _api_get(path: str, params: dict | None = None) -> dict:
    import httpx
    url     = f"{_API_URL}{path}"
    headers = {"Authorization": f"Bearer {_API_TOKEN}"}
    try:
        r = httpx.get(url, params=params or {}, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


# ── Tool implementations (direct import path when no API URL) ───────────

def _nexus_query(question: str, session_id: str = "") -> str:
    if _API_URL:
        result = _api_post("/v1/query", {"question": question, "session_id": session_id})
    else:
        from nexus.agents.guard       import check_intent, build_security_filter
        from nexus.core.nl_to_sparql  import nl_to_sparql
        from nexus.core.stardog_client import get_stardog
        from nexus.core.answer_engine  import synthesise_full
        from nexus.audit.pii_scanner   import scan_and_redact

        guard = check_intent(question, "analyst")
        if not guard.allowed:
            return f"Blocked: {guard.reason}"
        sec    = build_security_filter("analyst")
        sparql = nl_to_sparql(question, extra_filters=sec.sparql_data_filter, session_id=session_id)
        db     = get_stardog()
        _, rows = db.to_rows(db.query(sparql))
        scan   = scan_and_redact(rows, redact=True)
        res    = synthesise_full(question, [], scan.redacted_rows, sparql, len(rows))
        return res.answer

    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("answer", json.dumps(result))


def _nexus_impact(entity: str, change_type: str = "Decommission") -> str:
    result = _api_post("/v1/impact/analyze", {"entity": entity, "change_type": change_type})
    if "error" in result:
        return f"Error: {result['error']}"
    rings   = result.get("rings", [])
    summary = [f"Risk level: {result.get('risk_level', '?')}"]
    summary += [f"  {r['icon']} {r['label']}: {r['count']} affected" for r in rings]
    summary.append(result.get("narrative", ""))
    return "\n".join(summary)


def _nexus_apm(focus_domain: str = "") -> str:
    result = _api_post("/v1/apm/analyze", {"focus_domain": focus_domain})
    if "error" in result:
        return f"Error: {result['error']}"
    health  = result.get("portfolio_health", "?")
    summary = result.get("time_summary", {})
    themes  = result.get("investment_themes", [])
    return (
        f"Portfolio Health: {health}/100\n"
        f"TIME breakdown: {json.dumps(summary)}\n"
        f"Investment themes: {', '.join(themes[:3])}\n"
        f"{result.get('executive_summary', '')}"
    )


def _nexus_sa_advisor(focus_domain: str = "") -> str:
    result = _api_post("/v1/sa-advisor", {"focus_domain": focus_domain})
    if "error" in result:
        return f"Error: {result['error']}"
    score = result.get("architecture_health_score", "?")
    recs  = result.get("recommendations", [])[:3]
    out   = [f"Architecture Health: {score}/100", result.get("executive_summary", "")]
    out  += [f"• [{r['priority']}] {r['title']}: {r['action']}" for r in recs]
    return "\n".join(out)


def _nexus_diagram(diagram_type: str, entity: str = "", fmt: str = "mermaid") -> str:
    result = _api_post("/v1/artifact/diagram", {
        "diagram_type": diagram_type, "entity": entity, "fmt": fmt,
        "depth": 2, "max_nodes": 40,
    })
    if "error" in result:
        return f"Error: {result['error']}"
    return (
        f"Diagram: {result.get('title', diagram_type)} "
        f"({result.get('node_count', 0)} nodes, {result.get('edge_count', 0)} edges)\n\n"
        f"```{result.get('fmt', 'text')}\n{result.get('content', '')}\n```"
    )


def _nexus_assert_finding(label: str, severity: str, asset_uri: str, description: str) -> str:
    result = _api_post("/v1/assert", {
        "agent_id": "gigi-glean", "label": label, "severity": severity,
        "asset_uri": asset_uri, "description": description,
    })
    if "error" in result:
        return f"Error: {result['error']}"
    return f"Finding asserted: {result.get('finding_uri', '?')}"


def _nexus_entity(entity: str) -> str:
    result = _api_post("/v1/context", {"entity": entity})
    if "error" in result:
        return f"Error: {result['error']}"
    return json.dumps(result, indent=2, default=str)[:3000]


def _nexus_adrs(capability: str = "", domain: str = "") -> str:
    params = {}
    if capability:
        params["capability"] = capability
    if domain:
        params["domain"] = domain
    result = _api_get("/v1/adr/list", params)
    if "error" in result:
        return f"Error: {result['error']}"
    adrs = result.get("adrs", [])
    if not adrs:
        return "No ADRs found."
    lines = [f"• {a.get('title', a.get('uri', '?'))} — {a.get('domain', '')} / {a.get('capability', '')}" for a in adrs[:10]]
    return f"Found {len(adrs)} ADR(s):\n" + "\n".join(lines)


def _nexus_health() -> str:
    result = _api_get("/v1/health/graph")
    if "error" in result:
        return f"Error: {result['error']}"
    status  = result.get("status", "?")
    metrics = result.get("metrics", {})
    lines   = [f"Status: {status}"]
    lines  += [f"  {k}: {v}" for k, v in metrics.items()]
    return "\n".join(lines)


# ── MCP Server ──────────────────────────────────────────────────────────

def build_mcp_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "nexus-kg",
        instructions=(
            "NEXUS is the enterprise knowledge graph for architecture, application portfolio, "
            "AI governance, and change impact analysis. Use these tools to answer questions "
            "about enterprise applications, business capabilities, data assets, AI agents, "
            "and architectural decisions."
        ),
    )

    @mcp.tool()
    def nexus_query(question: str, session_id: str = "") -> str:
        """
        Ask a natural language question about the enterprise architecture knowledge graph.
        Examples: 'Which apps support Order-to-Cash?', 'Who owns the Finance data products?',
        'What AI agents have access to Restricted data?'
        """
        return _nexus_query(question, session_id)

    @mcp.tool()
    def nexus_impact_analyze(entity: str, change_type: str = "Decommission") -> str:
        """
        Compute the blast radius of a proposed change to an application, capability, or asset.
        change_type options: Decommission | Re-platform | Major version upgrade |
        Owner change | Data classification change | Integration removal
        """
        return _nexus_impact(entity, change_type)

    @mcp.tool()
    def nexus_apm_analyze(focus_domain: str = "") -> str:
        """
        Run a Gartner TIME model portfolio analysis.
        Returns portfolio health score, TIME breakdown (Tolerate/Invest/Migrate/Eliminate),
        and investment themes. Optionally filter by domain (e.g. 'finance', 'hr').
        """
        return _nexus_apm(focus_domain)

    @mcp.tool()
    def nexus_sa_advisor(focus_domain: str = "") -> str:
        """
        Get Solutions Architecture recommendations for a domain.
        Returns architecture health score, capability gaps, tech debt, and prioritised actions.
        """
        return _nexus_sa_advisor(focus_domain)

    @mcp.tool()
    def nexus_generate_diagram(
        diagram_type: str,
        entity: str = "",
        fmt: str = "mermaid",
    ) -> str:
        """
        Generate an architecture diagram from the knowledge graph.
        diagram_type: dependency | capability_map | data_lineage | agent_ecosystem |
                      c4_context | org_ownership | integration
        entity: required for c4_context and data_lineage
        fmt: mermaid (default) | dot
        """
        return _nexus_diagram(diagram_type, entity, fmt)

    @mcp.tool()
    def nexus_assert_finding(
        label: str,
        severity: str,
        asset_uri: str,
        description: str,
    ) -> str:
        """
        Record an architectural finding or risk to the knowledge graph.
        severity: Low | Medium | High | Critical
        asset_uri: The URI of the affected asset.
        """
        return _nexus_assert_finding(label, severity, asset_uri, description)

    @mcp.tool()
    def nexus_get_entity(entity: str) -> str:
        """
        Get the full context bundle for a named entity: properties, related entities,
        governance rules, and open findings.
        entity: name of an application, capability, agent, or data asset.
        """
        return _nexus_entity(entity)

    @mcp.tool()
    def nexus_list_adrs(capability: str = "", domain: str = "") -> str:
        """
        List Architecture Decision Records from the knowledge graph.
        Optionally filter by capability name or domain name.
        """
        return _nexus_adrs(capability, domain)

    @mcp.tool()
    def nexus_graph_health() -> str:
        """
        Check NEXUS knowledge graph health metrics:
        total triples, entity counts, open findings, orphaned apps, capability gaps.
        """
        return _nexus_health()

    return mcp


def main():
    logging.basicConfig(level=logging.WARNING)
    mcp = build_mcp_server()
    mcp.run()


if __name__ == "__main__":
    main()
