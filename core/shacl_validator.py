"""
core/shacl_validator.py — SPARQL-based SHACL constraint validation for NEXUS.

Each shape is implemented as a SPARQL SELECT that returns violations.
Pass = zero rows returned. Checks mirror the sh:NodeShapes in
domains/sap_migration_ontology.ttl.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

KPI_BASE  = "https://ontology.ea.example.org/kpi#"
MIG_BASE  = "https://ontology.ea.example.org/migration#"

_PREFIXES = f"""
PREFIX kpi:  <{KPI_BASE}>
PREFIX mig:  <{MIG_BASE}>
PREFIX bw:   <https://ontology.ea.example.org/bw#>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
"""

# ── Shape definitions ────────────────────────────────────────────────────────
# Each entry: (shape_id, label, severity, sparql_for_violations)
# The SPARQL must SELECT ?subject ?label (and optionally ?detail).
# Zero rows = passes. Any row = violation with subject + label.

_SHAPES: list[tuple[str, str, str, str]] = [
    (
        "S1",
        "ToNEXUS reports must have a Competency Question",
        "High",
        f"""
{_PREFIXES}
SELECT ?subject ?label WHERE {{
  ?subject mig:approvedDisposition mig:ToNEXUS .
  OPTIONAL {{ ?subject rdfs:label ?label }}
  FILTER NOT EXISTS {{ ?subject mig:hasCompetencyQuestion ?cq }}
}}
""",
    ),
    (
        "S2",
        "CalculatedMeasure must declare kpi:expression",
        "High",
        f"""
{_PREFIXES}
SELECT ?subject ?label WHERE {{
  ?subject a kpi:CalculatedMeasure .
  OPTIONAL {{ ?subject rdfs:label ?label }}
  FILTER NOT EXISTS {{ ?subject kpi:expression ?e . FILTER(?e != "") }}
}}
""",
    ),
    (
        "S3",
        "KPI must be attributed to an owner (prov:wasAttributedTo)",
        "Medium",
        f"""
{_PREFIXES}
SELECT ?subject ?label WHERE {{
  ?subject a kpi:KPI .
  OPTIONAL {{ ?subject rdfs:label ?label }}
  FILTER NOT EXISTS {{ ?subject prov:wasAttributedTo ?owner }}
}}
""",
    ),
    (
        "S4",
        "DataProduct must have dcat:distribution",
        "High",
        f"""
{_PREFIXES}
SELECT ?subject ?label WHERE {{
  ?subject a kpi:DataProduct .
  OPTIONAL {{ ?subject rdfs:label ?label }}
  FILTER NOT EXISTS {{ ?subject dcat:distribution ?dist }}
}}
""",
    ),
    (
        "S5",
        "LegacyReport should have a proposed or approved disposition",
        "Low",
        f"""
{_PREFIXES}
SELECT ?subject ?label WHERE {{
  ?subject a mig:LegacyReport .
  OPTIONAL {{ ?subject rdfs:label ?label }}
  FILTER NOT EXISTS {{
    {{ ?subject mig:proposedDisposition ?d }}
    UNION
    {{ ?subject mig:approvedDisposition ?d }}
  }}
}}
""",
    ),
    (
        "S6",
        "BDC+Databricks reports must point to a Unity Catalog object (dcat:distribution)",
        "High",
        f"""
{_PREFIXES}
SELECT ?subject ?label WHERE {{
  ?subject mig:approvedDisposition mig:ToBDCDatabricks .
  OPTIONAL {{ ?subject rdfs:label ?label }}
  FILTER NOT EXISTS {{ ?subject dcat:distribution ?dist }}
}}
""",
    ),
]


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class ShapeViolation:
    subject: str
    label:   str


@dataclass
class ShapeResult:
    shape_id:   str
    label:      str
    severity:   str
    passed:     bool
    violations: list[ShapeViolation] = field(default_factory=list)
    error:      str | None = None


@dataclass
class ValidationReport:
    passed:       bool
    shape_results: list[ShapeResult]
    total_shapes:  int
    pass_count:    int
    fail_count:    int
    error_count:   int

    def summary(self) -> str:
        return (
            f"{self.pass_count}/{self.total_shapes} shapes passed, "
            f"{self.fail_count} failed, {self.error_count} errors."
        )


# ── Validator ────────────────────────────────────────────────────────────────

def validate(shapes: list[str] | None = None) -> ValidationReport:
    """
    Run SHACL-equivalent SPARQL checks against the NEXUS graph.

    Args:
        shapes: Optional list of shape IDs (e.g. ["S1", "S3"]) to run.
                Defaults to all shapes.

    Returns:
        ValidationReport with per-shape results.
    """
    from nexus.core.stardog_client import get_stardog

    db = get_stardog()
    results: list[ShapeResult] = []

    target_shapes = _SHAPES
    if shapes:
        target_shapes = [s for s in _SHAPES if s[0] in shapes]

    for shape_id, label, severity, sparql in target_shapes:
        try:
            _, rows = db.to_rows(db.query(sparql.strip(), inject_prefixes=False))
            violations = [
                ShapeViolation(
                    subject=r.get("subject", ""),
                    label=r.get("label", r.get("subject", "").split("#")[-1]),
                )
                for r in rows
            ]
            results.append(ShapeResult(
                shape_id=shape_id,
                label=label,
                severity=severity,
                passed=len(violations) == 0,
                violations=violations,
            ))
        except Exception as exc:
            logger.warning("Shape %s failed to execute: %s", shape_id, exc)
            results.append(ShapeResult(
                shape_id=shape_id,
                label=label,
                severity=severity,
                passed=False,
                error=str(exc),
            ))

    pass_count  = sum(1 for r in results if r.passed and r.error is None)
    fail_count  = sum(1 for r in results if not r.passed and r.error is None)
    error_count = sum(1 for r in results if r.error is not None)

    return ValidationReport(
        passed        = fail_count == 0 and error_count == 0,
        shape_results = results,
        total_shapes  = len(results),
        pass_count    = pass_count,
        fail_count    = fail_count,
        error_count   = error_count,
    )
