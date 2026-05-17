from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    severity: str       # Critical | High | Medium | Low
    category: str       # required_property | data_quality | referential | governance
    entity_uri: str
    entity_label: str
    issue: str
    sparql: str


@dataclass
class ValidationReport:
    validated_at: str
    total_issues: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    issues: list[ValidationIssue]
    shacl_summary: str
    passed: bool        # True only when zero Critical/High issues


def _get_db():
    from nexus.core.stardog_client import get_stardog
    return get_stardog()


def _run_query(sparql: str) -> list[dict[str, str]]:
    db = _get_db()
    _, rows = db.to_rows(db.query(sparql, inject_prefixes=True))
    return rows


# ── Individual checks ─────────────────────────────────────────────────────────

def check_required_properties() -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    checks = [
        (
            "app:Application",
            "app:lifecycle",
            "Application missing app:lifecycle",
            """
            SELECT ?e ?label WHERE {
                ?e a app:Application .
                OPTIONAL { ?e rdfs:label ?label }
                FILTER NOT EXISTS { ?e app:lifecycle ?v }
            } LIMIT 100
            """,
        ),
        (
            "app:Application",
            "rdfs:label",
            "Application missing rdfs:label",
            """
            SELECT ?e (str(?e) as ?label) WHERE {
                ?e a app:Application .
                FILTER NOT EXISTS { ?e rdfs:label ?v }
            } LIMIT 100
            """,
        ),
        (
            "ai:Agent",
            "rdfs:label",
            "AI Agent missing rdfs:label",
            """
            SELECT ?e (str(?e) as ?label) WHERE {
                ?e a ai:Agent .
                FILTER NOT EXISTS { ?e rdfs:label ?v }
            } LIMIT 100
            """,
        ),
        (
            "ai:Agent",
            "ai:riskTier",
            "AI Agent missing ai:riskTier",
            """
            SELECT ?e ?label WHERE {
                ?e a ai:Agent .
                OPTIONAL { ?e rdfs:label ?label }
                FILTER NOT EXISTS { ?e ai:riskTier ?v }
            } LIMIT 100
            """,
        ),
        (
            "data:DataProduct",
            "rdfs:label",
            "DataProduct missing rdfs:label",
            """
            SELECT ?e (str(?e) as ?label) WHERE {
                ?e a data:DataProduct .
                FILTER NOT EXISTS { ?e rdfs:label ?v }
            } LIMIT 100
            """,
        ),
        (
            "data:DataProduct",
            "data:classification",
            "DataProduct missing data:classification",
            """
            SELECT ?e ?label WHERE {
                ?e a data:DataProduct .
                OPTIONAL { ?e rdfs:label ?label }
                FILTER NOT EXISTS { ?e data:classification ?v }
            } LIMIT 100
            """,
        ),
    ]

    for rdf_type, prop, description, sparql in checks:
        try:
            rows = _run_query(sparql.strip())
        except Exception as exc:
            logger.warning("check_required_properties query failed (%s): %s", prop, exc)
            continue
        for row in rows:
            uri = row.get("e", "")
            label = row.get("label", uri.split("#")[-1] if uri else "unknown")
            issues.append(ValidationIssue(
                severity="High",
                category="required_property",
                entity_uri=uri,
                entity_label=label,
                issue=description,
                sparql=sparql.strip(),
            ))

    return issues


def check_duplicate_labels() -> list[ValidationIssue]:
    sparql = """
    SELECT ?type ?label (COUNT(?e) as ?count) WHERE {
        ?e a ?type ; rdfs:label ?label .
        FILTER(?type IN (app:Application, ea:BusinessCapabilityL3, data:DataProduct))
    } GROUP BY ?type ?label HAVING(COUNT(?e) > 1)
    """.strip()

    issues: list[ValidationIssue] = []
    try:
        rows = _run_query(sparql)
    except Exception as exc:
        logger.warning("check_duplicate_labels failed: %s", exc)
        return issues

    for row in rows:
        rdf_type = row.get("type", "")
        label = row.get("label", "")
        count = row.get("count", "?")
        issues.append(ValidationIssue(
            severity="Medium",
            category="data_quality",
            entity_uri=rdf_type,
            entity_label=label,
            issue=f'Duplicate label "{label}" found {count} times for type {rdf_type.split("#")[-1]}',
            sparql=sparql,
        ))

    return issues


def check_referential_integrity() -> list[ValidationIssue]:
    sparql = """
    SELECT ?app ?appLabel ?dep WHERE {
        ?app app:dependsOn ?dep .
        OPTIONAL { ?app rdfs:label ?appLabel }
        FILTER NOT EXISTS { ?dep a ?anyType }
    } LIMIT 50
    """.strip()

    issues: list[ValidationIssue] = []
    try:
        rows = _run_query(sparql)
    except Exception as exc:
        logger.warning("check_referential_integrity failed: %s", exc)
        return issues

    for row in rows:
        uri = row.get("app", "")
        label = row.get("appLabel", uri.split("#")[-1] if uri else "unknown")
        dep = row.get("dep", "unknown")
        issues.append(ValidationIssue(
            severity="High",
            category="referential",
            entity_uri=uri,
            entity_label=label,
            issue=f"app:dependsOn points to non-existent entity: {dep}",
            sparql=sparql,
        ))

    return issues


def check_governance_completeness() -> list[ValidationIssue]:
    sparql = """
    SELECT ?app ?appLabel WHERE {
        ?app a app:Application ;
             app:lifecycle "production" .
        OPTIONAL { ?app rdfs:label ?appLabel }
        FILTER NOT EXISTS { ?app app:owner ?o }
    } LIMIT 30
    """.strip()

    issues: list[ValidationIssue] = []
    try:
        rows = _run_query(sparql)
    except Exception as exc:
        logger.warning("check_governance_completeness failed: %s", exc)
        return issues

    for row in rows:
        uri = row.get("app", "")
        label = row.get("appLabel", uri.split("#")[-1] if uri else "unknown")
        issues.append(ValidationIssue(
            severity="Critical",
            category="governance",
            entity_uri=uri,
            entity_label=label,
            issue="Production application has no owner assigned",
            sparql=sparql,
        ))

    return issues


def run_shacl() -> str:
    try:
        from nexus.core.shacl_validator import validate
        result = validate()
        return result.summary()
    except Exception as exc:
        return f"SHACL validation skipped: {exc}"


def run_full_validation() -> ValidationReport:
    all_issues: list[ValidationIssue] = []

    for check_fn in (
        check_required_properties,
        check_duplicate_labels,
        check_referential_integrity,
        check_governance_completeness,
    ):
        try:
            all_issues.extend(check_fn())
        except Exception as exc:
            logger.error("Validation check %s raised: %s", check_fn.__name__, exc)

    severity_order = ["Critical", "High", "Medium", "Low"]
    by_severity: dict[str, int] = {s: 0 for s in severity_order}
    by_category: dict[str, int] = {}

    for issue in all_issues:
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        by_category[issue.category] = by_category.get(issue.category, 0) + 1

    blocking = by_severity.get("Critical", 0) + by_severity.get("High", 0)

    return ValidationReport(
        validated_at=datetime.now(timezone.utc).isoformat(),
        total_issues=len(all_issues),
        by_severity=by_severity,
        by_category=by_category,
        issues=all_issues,
        shacl_summary=run_shacl(),
        passed=blocking == 0,
    )
