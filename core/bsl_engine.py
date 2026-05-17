"""core/bsl_engine.py — Business Semantic Layer: KPI and rule retrieval/evaluation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_KPI_SPARQL = """
SELECT ?kpi ?label ?domain ?formula ?sql ?unit ?owner ?desc WHERE {
    ?kpi a bsl:KPI .
    OPTIONAL { ?kpi rdfs:label ?label }
    OPTIONAL { ?kpi bsl:domain ?domain }
    OPTIONAL { ?kpi bsl:formula ?formula }
    OPTIONAL { ?kpi bsl:databricksSQL ?sql }
    OPTIONAL { ?kpi bsl:unit ?unit }
    OPTIONAL { ?kpi bsl:owner ?owner }
    OPTIONAL { ?kpi rdfs:comment ?desc }
    FILTER(?domain = "{domain}" || "{domain}" = "")
}
"""

_RULE_SPARQL = """
SELECT ?rule ?label ?domain ?ruleText ?sparqlCheck ?severity WHERE {
    ?rule a bsl:BusinessRule .
    OPTIONAL { ?rule rdfs:label ?label }
    OPTIONAL { ?rule bsl:domain ?domain }
    OPTIONAL { ?rule bsl:ruleText ?ruleText }
    OPTIONAL { ?rule bsl:sparqlCheck ?sparqlCheck }
    OPTIONAL { ?rule bsl:severity ?severity }
}
"""

_VIOLATION_SPARQL_TEMPLATE = """
SELECT ?entity ?entityLabel WHERE {{
    {body}
}}
"""


@dataclass
class KpiDefinition:
    uri: str
    label: str
    domain: str
    formula: str
    databricks_sql: str
    unit: str
    owner: str
    description: str


@dataclass
class KpiValue:
    kpi_uri: str
    label: str
    value: Any
    unit: str
    evaluated_at: str
    error: str = ""


@dataclass
class BusinessRule:
    uri: str
    label: str
    domain: str
    rule_text: str
    sparql_check: str
    severity: str


@dataclass
class RuleViolation:
    rule_uri: str
    rule_label: str
    severity: str
    entity_uri: str
    entity_label: str
    detail: str


def list_kpis(domain: str = "") -> list[KpiDefinition]:
    """Query graph for bsl:KPI instances, optionally filtered by domain."""
    from nexus.core.stardog_client import get_stardog
    db = get_stardog()
    sparql = _KPI_SPARQL.format(domain=domain)
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("bsl list_kpis failed: %s", exc)
        return []
    return [
        KpiDefinition(
            uri=r.get("kpi", ""),
            label=r.get("label", ""),
            domain=r.get("domain", ""),
            formula=r.get("formula", ""),
            databricks_sql=r.get("sql", ""),
            unit=r.get("unit", ""),
            owner=r.get("owner", ""),
            description=r.get("desc", ""),
        )
        for r in rows
    ]


def evaluate_kpi(kpi_uri: str) -> KpiValue:
    """Fetch KPI definition from graph then run its databricks_sql."""
    ts = datetime.now(timezone.utc).isoformat()
    matches = [k for k in list_kpis() if k.uri == kpi_uri]
    if not matches:
        return KpiValue(kpi_uri=kpi_uri, label=kpi_uri, value=None, unit="", evaluated_at=ts, error="KPI not found")

    kpi = matches[0]
    if not kpi.databricks_sql.strip():
        return KpiValue(kpi_uri=kpi_uri, label=kpi.label, value=None, unit=kpi.unit, evaluated_at=ts, error="No SQL defined")

    from nexus.core.databricks_client import get_databricks
    try:
        db = get_databricks()
        cols, rows = db.query(kpi.databricks_sql)
        value = rows[0][cols[0]] if rows and cols else None
    except Exception as exc:
        logger.warning("evaluate_kpi %s failed: %s", kpi_uri, exc)
        return KpiValue(kpi_uri=kpi_uri, label=kpi.label, value=None, unit=kpi.unit, evaluated_at=ts, error=str(exc))

    return KpiValue(kpi_uri=kpi_uri, label=kpi.label, value=value, unit=kpi.unit, evaluated_at=ts)


def list_rules(domain: str = "") -> list[BusinessRule]:
    """Query graph for bsl:BusinessRule instances."""
    from nexus.core.stardog_client import get_stardog
    db = get_stardog()
    sparql = _RULE_SPARQL
    if domain:
        sparql += f'\nFILTER(?domain = "{domain}")\n'
    try:
        raw = db.query(sparql, inject_prefixes=True)
        _, rows = db.to_rows(raw)
    except Exception as exc:
        logger.warning("bsl list_rules failed: %s", exc)
        return []
    return [
        BusinessRule(
            uri=r.get("rule", ""),
            label=r.get("label", ""),
            domain=r.get("domain", ""),
            rule_text=r.get("ruleText", ""),
            sparql_check=r.get("sparqlCheck", ""),
            severity=r.get("severity", "Medium"),
        )
        for r in rows
    ]


def check_rules(entity_uri: str = "", domain: str = "") -> list[RuleViolation]:
    """Run all rule SPARQL ASK checks, return violations."""
    from nexus.core.stardog_client import get_stardog
    db = get_stardog()

    rules = list_rules(domain=domain)
    if not rules:
        return []

    violations: list[RuleViolation] = []
    for rule in rules:
        if not rule.sparql_check.strip():
            continue
        check = rule.sparql_check.strip()
        # Determine if this is a SELECT with ?entity/?entityLabel or a bare ASK/SELECT body
        upper = check.upper()
        try:
            if upper.startswith("ASK"):
                raw = db.query(check, inject_prefixes=True)
                _, rows = db.to_rows(raw)
                triggered = rows[0]["result"].lower() == "true" if rows else False
                if triggered:
                    violations.append(RuleViolation(
                        rule_uri=rule.uri,
                        rule_label=rule.label,
                        severity=rule.severity,
                        entity_uri=entity_uri,
                        entity_label=entity_uri,
                        detail=rule.rule_text,
                    ))
            elif "?ENTITY" in upper and "?ENTITYLABEL" in upper:
                # Already a full SELECT that yields ?entity ?entityLabel
                raw = db.query(check, inject_prefixes=True)
                _, rows = db.to_rows(raw)
                for row in rows:
                    ent = row.get("entity", "")
                    if entity_uri and ent != entity_uri:
                        continue
                    violations.append(RuleViolation(
                        rule_uri=rule.uri,
                        rule_label=rule.label,
                        severity=rule.severity,
                        entity_uri=ent,
                        entity_label=row.get("entityLabel", ent),
                        detail=rule.rule_text,
                    ))
            else:
                # Treat as a WHERE body and wrap it
                wrapped = _VIOLATION_SPARQL_TEMPLATE.format(body=check)
                raw = db.query(wrapped, inject_prefixes=True)
                _, rows = db.to_rows(raw)
                for row in rows:
                    ent = row.get("entity", "")
                    if entity_uri and ent != entity_uri:
                        continue
                    violations.append(RuleViolation(
                        rule_uri=rule.uri,
                        rule_label=rule.label,
                        severity=rule.severity,
                        entity_uri=ent,
                        entity_label=row.get("entityLabel", ent),
                        detail=rule.rule_text,
                    ))
        except Exception as exc:
            logger.warning("Rule check %s failed: %s", rule.uri, exc)

    return violations


def evaluate_all_kpis(domain: str = "") -> list[KpiValue]:
    """Evaluate all KPIs (or filtered by domain)."""
    return [evaluate_kpi(k.uri) for k in list_kpis(domain=domain)]
