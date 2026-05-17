"""core/scenario_engine.py — What-if scenario simulation for enterprise architecture."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from nexus.core.stardog_client import get_stardog
from nexus.core.claude_client import quick_complete

logger = logging.getLogger(__name__)

_VALID_ACTIONS = frozenset({"decommission", "merge", "upgrade", "replace"})


@dataclass
class ScenarioResult:
    entity: str
    entity_label: str
    action: str
    at_risk_apps: list[dict]
    at_risk_capabilities: list[dict]
    at_risk_data_products: list[dict]
    risk_score: int
    narrative: str
    recommendations: list[str]


def _resolve_uri(db, entity: str) -> tuple[str, str]:
    """Return (uri, label). If entity looks like a URI, use it directly."""
    if entity.startswith("http") or entity.startswith("urn") or entity.startswith("<"):
        uri = entity.strip("<>")
        label_sparql = f"""
        SELECT ?label WHERE {{
            <{uri}> rdfs:label ?label .
        }} LIMIT 1
        """
        try:
            raw = db.query(label_sparql, inject_prefixes=True)
            _, rows = db.to_rows(raw)
            label = rows[0][0] if rows else uri
        except Exception:
            label = uri
        return uri, label

    lookup = f"""
    SELECT ?entity ?label WHERE {{
        ?entity rdfs:label ?label .
        FILTER(LCASE(STR(?label)) = LCASE("{entity}"))
    }} LIMIT 1
    """
    try:
        raw = db.query(lookup, inject_prefixes=True)
        _, rows = db.to_rows(raw)
        if rows:
            return rows[0][0], rows[0][1] if len(rows[0]) > 1 else entity
    except Exception as exc:
        logger.warning("URI resolution failed for %r: %s", entity, exc)

    # Fuzzy fallback
    fuzzy = f"""
    SELECT ?entity ?label WHERE {{
        ?entity rdfs:label ?label .
        FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{entity}")))
    }} LIMIT 1
    """
    try:
        raw = db.query(fuzzy, inject_prefixes=True)
        _, rows = db.to_rows(raw)
        if rows:
            return rows[0][0], rows[0][1] if len(rows[0]) > 1 else entity
    except Exception as exc:
        logger.warning("Fuzzy URI resolution failed for %r: %s", entity, exc)

    return entity, entity


def _query_dependencies(db, entity_uri: str) -> list[dict]:
    sparql = f"""
    SELECT ?dep ?depLabel ?rel WHERE {{
        {{
            <{entity_uri}> ?rel ?dep .
        }} UNION {{
            ?dep ?rel <{entity_uri}> .
        }}
        OPTIONAL {{ ?dep rdfs:label ?depLabel }}
        FILTER(?rel IN (
            app:dependsOn,
            app:integratesWith,
            ea:enablesBusinessCapability,
            data:consumes,
            data:produces
        ))
    }}
    """
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("dependency query failed for <%s>: %s", entity_uri, exc)
        return []

    deps = []
    for row in rows:
        dep_uri = row[0] if row[0] else ""
        dep_label = row[1] if len(row) > 1 and row[1] else dep_uri
        rel = row[2] if len(row) > 2 and row[2] else "unknown"
        deps.append({"uri": dep_uri, "label": dep_label, "relationship": rel})
    return deps


def _classify_deps(deps: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split deps into (apps, capabilities, data_products) by URI heuristics."""
    apps, caps, data = [], [], []
    for d in deps:
        uri_lower = d["uri"].lower()
        rel_lower = d["relationship"].lower()
        if "application" in uri_lower or "app" in rel_lower or "integrates" in rel_lower or "dependson" in rel_lower:
            apps.append(d)
        elif "capability" in uri_lower or "capability" in rel_lower:
            caps.append(d)
        elif "data" in uri_lower or "dataproduct" in uri_lower or "consumes" in rel_lower or "produces" in rel_lower:
            data.append(d)
        else:
            apps.append(d)
    return apps, caps, data


def run_scenario(
    entity: str,
    action: str,
    params: dict | None = None,
    user_role: str = "analyst",
) -> ScenarioResult:
    if action not in _VALID_ACTIONS:
        raise ValueError(f"action must be one of {sorted(_VALID_ACTIONS)}, got {action!r}")

    params = params or {}
    db = get_stardog()

    entity_uri, entity_label = _resolve_uri(db, entity)
    deps = _query_dependencies(db, entity_uri)
    at_risk_apps, at_risk_capabilities, at_risk_data = _classify_deps(deps)

    risk_score = min(
        100,
        len(at_risk_apps) * 15
        + len(at_risk_capabilities) * 10
        + len(at_risk_data) * 8,
    )

    replace_context = ""
    if action == "replace" and params.get("replace_with"):
        replace_context = f" with {params['replace_with']}"

    narrative_prompt = (
        f"An enterprise architect is evaluating the following scenario:\n"
        f"Action: {action}{replace_context} '{entity_label}'\n"
        f"At-risk applications ({len(at_risk_apps)}): {[a['label'] for a in at_risk_apps[:5]]}\n"
        f"At-risk capabilities ({len(at_risk_capabilities)}): {[c['label'] for c in at_risk_capabilities[:5]]}\n"
        f"At-risk data products ({len(at_risk_data)}): {[d['label'] for d in at_risk_data[:5]]}\n"
        f"Risk score: {risk_score}/100\n\n"
        f"Describe the impact of this scenario in 2-3 sentences and list 3 concrete recommendations."
    )

    raw_narrative = quick_complete(
        "You are a senior enterprise architect. Be concise and actionable.",
        narrative_prompt,
        max_tokens=400,
    )

    # Split narrative and recommendations heuristically
    narrative = raw_narrative
    recommendations: list[str] = []
    if raw_narrative:
        lines = [ln.strip() for ln in raw_narrative.splitlines() if ln.strip()]
        rec_lines = [ln for ln in lines if ln[:1].isdigit() or ln.startswith("-") or ln.startswith("•")]
        if rec_lines:
            recommendations = [ln.lstrip("0123456789.-•) ") for ln in rec_lines[:3]]
            narrative_lines = [ln for ln in lines if ln not in rec_lines]
            narrative = " ".join(narrative_lines)

    return ScenarioResult(
        entity=entity_uri,
        entity_label=entity_label,
        action=action,
        at_risk_apps=at_risk_apps,
        at_risk_capabilities=at_risk_capabilities,
        at_risk_data_products=at_risk_data,
        risk_score=risk_score,
        narrative=narrative,
        recommendations=recommendations,
    )
