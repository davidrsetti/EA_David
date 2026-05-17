"""core/gap_analyzer.py — Architectural gap analysis across 5 dimensions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from nexus.core.stardog_client import get_stardog
from nexus.core.claude_client import quick_complete

logger = logging.getLogger(__name__)


@dataclass
class GapItem:
    category: str
    uri: str
    label: str
    severity: str
    detail: str


@dataclass
class GapAnalysis:
    analyzed_at: str
    total_gaps: int
    by_category: dict[str, int]
    gaps: list[GapItem]
    summary: str


def analyze_capability_gaps(db) -> list[GapItem]:
    sparql = """
    SELECT ?cap ?capLabel WHERE {
        ?cap a ea:BusinessCapabilityL3 .
        OPTIONAL { ?cap rdfs:label ?capLabel }
        FILTER NOT EXISTS { ?app ea:enablesBusinessCapability ?cap }
    } LIMIT 50
    """
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("capability gap query failed: %s", exc)
        return []

    items = []
    for row in rows:
        uri = row[0] if row[0] else ""
        label = row[1] if len(row) > 1 and row[1] else uri
        items.append(GapItem(
            category="capability",
            uri=uri,
            label=label,
            severity="Medium",
            detail="Business capability has no supporting application.",
        ))
    return items


def analyze_orphaned_apps(db) -> list[GapItem]:
    sparql = """
    SELECT ?app ?appLabel WHERE {
        ?app a app:Application .
        OPTIONAL { ?app rdfs:label ?appLabel }
        FILTER NOT EXISTS { ?app ea:enablesBusinessCapability ?cap }
        FILTER NOT EXISTS { ?app app:supportedByCapability ?cap }
    } LIMIT 50
    """
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("orphaned app query failed: %s", exc)
        return []

    items = []
    for row in rows:
        uri = row[0] if row[0] else ""
        label = row[1] if len(row) > 1 and row[1] else uri
        items.append(GapItem(
            category="orphan",
            uri=uri,
            label=label,
            severity="Medium",
            detail="Application has no capability mapping.",
        ))
    return items


def analyze_governance_gaps(db) -> list[GapItem]:
    sparql = """
    SELECT ?entity ?label ?type WHERE {
        { ?entity a app:Application } UNION { ?entity a ai:Agent }
        OPTIONAL { ?entity rdfs:label ?label }
        OPTIONAL { ?entity a ?type }
        FILTER NOT EXISTS { ?entity app:lifecycle ?lc }
    } LIMIT 50
    """
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("governance gap query failed: %s", exc)
        return []

    seen: set[str] = set()
    items = []
    for row in rows:
        uri = row[0] if row[0] else ""
        if uri in seen:
            continue
        seen.add(uri)
        label = row[1] if len(row) > 1 and row[1] else uri
        items.append(GapItem(
            category="governance",
            uri=uri,
            label=label,
            severity="High",
            detail="Entity missing required lifecycle metadata.",
        ))
    return items


def analyze_data_gaps(db) -> list[GapItem]:
    sparql = """
    SELECT ?ds ?dsLabel WHERE {
        ?ds a data:DataProduct .
        OPTIONAL { ?ds rdfs:label ?dsLabel }
        FILTER NOT EXISTS { ?app data:consumes ?ds }
        FILTER NOT EXISTS { ?app data:produces ?ds }
    } LIMIT 50
    """
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("data gap query failed: %s", exc)
        return []

    items = []
    for row in rows:
        uri = row[0] if row[0] else ""
        label = row[1] if len(row) > 1 and row[1] else uri
        items.append(GapItem(
            category="data",
            uri=uri,
            label=label,
            severity="Medium",
            detail="Data product not linked to any application.",
        ))
    return items


def analyze_integration_gaps(db) -> list[GapItem]:
    sparql = """
    SELECT ?app1 ?label1 ?domain WHERE {
        ?app1 a app:Application ; ea:domain ?domain .
        OPTIONAL { ?app1 rdfs:label ?label1 }
        FILTER NOT EXISTS { ?app1 app:integratesWith ?any }
        FILTER NOT EXISTS { ?app1 app:dependsOn ?any2 }
    } LIMIT 30
    """
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("integration gap query failed: %s", exc)
        return []

    items = []
    for row in rows:
        uri = row[0] if row[0] else ""
        label = row[1] if len(row) > 1 and row[1] else uri
        domain = row[2] if len(row) > 2 and row[2] else "unknown"
        items.append(GapItem(
            category="integration",
            uri=uri,
            label=label,
            severity="Low",
            detail=f"Application in domain '{domain}' has no integration path.",
        ))
    return items


def run_full_gap_analysis(user_role: str = "analyst") -> GapAnalysis:
    db = get_stardog()
    gaps: list[GapItem] = []

    for fn in (
        analyze_capability_gaps,
        analyze_orphaned_apps,
        analyze_governance_gaps,
        analyze_data_gaps,
        analyze_integration_gaps,
    ):
        gaps.extend(fn(db))

    total_gaps = len(gaps)
    by_category: dict[str, int] = {}
    for g in gaps:
        by_category[g.category] = by_category.get(g.category, 0) + 1

    if total_gaps == 0:
        return GapAnalysis(
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            total_gaps=0,
            by_category={},
            gaps=[],
            summary="No gaps detected.",
        )

    summary = quick_complete(
        "You are an enterprise architect. Summarise the following gap analysis findings in 2-3 sentences, highlighting the most critical issues.",
        f"Gaps found: {total_gaps} total. By category: {by_category}. Top gaps: {[g.label for g in gaps[:5]]}",
        max_tokens=200,
    )
    if not summary:
        summary = f"Found {total_gaps} gaps across {len(by_category)} categories."

    return GapAnalysis(
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        total_gaps=total_gaps,
        by_category=by_category,
        gaps=gaps,
        summary=summary,
    )
