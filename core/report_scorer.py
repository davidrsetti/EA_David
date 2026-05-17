"""
core/report_scorer.py — PBI report disposition scoring engine.

Implements the 10-criterion weighted rubric from the Power BI → BDC/SAC/NEXUS
rationalisation playbook. Each criterion is scored 0–5; GxP is a boolean override.

Routing logic (in priority order):
  1. GxP = True           → SAC  (or Veeva Vault — out of NEXUS scope)
  2. C2 < 1 AND C3 > 4    → Retire
  3. C10 ≥ 4 AND C7 ≥ 4 AND C6 ≤ 3  → NEXUS
  4. C8 ≥ 4 AND C4 ≥ 3 AND C7 ≤ 3   → SAC
  5. C5 ≥ 4 OR C6 ≥ 4    → BDC+Databricks
  6. Otherwise            → SAC  (sanctioned SAP analytics default)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Criterion weights (C9 is boolean override — no weight in formula)
WEIGHTS: dict[str, int] = {
    "c1": 15, "c2": 15, "c3": 10, "c4": 10,
    "c5": 10, "c6": 10, "c7": 10, "c8": 10,
    "c10": 10,
}
DISPOSITION_RETIRE      = "Retire"
DISPOSITION_NEXUS       = "NEXUS"
DISPOSITION_SAC         = "SAC"
DISPOSITION_BDC         = "BDC+Databricks"

# Graph URI constants
MIG_BASE = "https://ontology.ea.example.org/migration#"


@dataclass
class ScoreResult:
    weighted_score:  float
    disposition:     str
    rationale:       str
    criteria_scores: dict[str, float]
    gxp:             bool = False
    triggered_rule:  str  = ""


def score_report(
    scores: dict[str, float],
    gxp: bool = False,
    report_label: str = "",
) -> ScoreResult:
    """
    Score a PBI report and return a disposition recommendation.

    Parameters
    ----------
    scores  : dict mapping criterion keys (c1..c10, excluding c9) to 0–5 floats.
              Missing criteria default to 0.
    gxp     : True if the report is GxP / regulated.
    report_label : Optional name for logging.

    Returns
    -------
    ScoreResult with weighted_score, disposition, rationale.
    """
    c = {k: float(scores.get(k, 0.0)) for k in ("c1","c2","c3","c4","c5","c6","c7","c8","c10")}

    # Weighted score (max 5.0)
    total_weight = sum(WEIGHTS.values())   # 100
    weighted = sum(c[k] * WEIGHTS[k] for k in WEIGHTS) / total_weight

    # ── Routing logic (priority order) ──────────────────────────────────
    if gxp:
        return ScoreResult(
            weighted_score=weighted, disposition=DISPOSITION_SAC,
            rationale="GxP override: regulated artefacts must use SAC/Datasphere or Veeva Vault.",
            criteria_scores=c, gxp=True, triggered_rule="C9-GxP",
        )

    if c["c2"] < 1 and c["c3"] > 4:
        return ScoreResult(
            weighted_score=weighted, disposition=DISPOSITION_RETIRE,
            rationale=f"No usage in 90 days (C2={c['c2']:.1f}) and fully duplicated by certified model (C3={c['c3']:.1f}).",
            criteria_scores=c, triggered_rule="C2+C3-Retire",
        )

    if c["c10"] >= 4 and c["c7"] >= 4 and c["c6"] <= 3:
        return ScoreResult(
            weighted_score=weighted, disposition=DISPOSITION_NEXUS,
            rationale=(
                f"High NEXUS alignment (C10={c['c10']:.1f}): questions are metadata/ownership/"
                f"KPI-definition style. Conversational pattern (C7={c['c7']:.1f}), modest data "
                f"volume (C6={c['c6']:.1f}) — ideal for NL→SPARQL + federated numeric queries."
            ),
            criteria_scores=c, triggered_rule="C10+C7+C6-NEXUS",
        )

    if c["c8"] >= 4 and c["c4"] >= 3 and c["c7"] <= 3:
        return ScoreResult(
            weighted_score=weighted, disposition=DISPOSITION_SAC,
            rationale=(
                f"Executive/board audience (C8={c['c8']:.1f}), SAP-native source (C4={c['c4']:.1f}), "
                f"story/dashboard pattern (C7={c['c7']:.1f}) — SAC live on Datasphere is the right fit."
            ),
            criteria_scores=c, triggered_rule="C8+C4+C7-SAC",
        )

    if c["c5"] >= 4 or c["c6"] >= 4:
        reason_parts = []
        if c["c5"] >= 4:
            reason_parts.append(f"high DAX/logic complexity (C5={c['c5']:.1f})")
        if c["c6"] >= 4:
            reason_parts.append(f"large data volume / sub-hour SLA (C6={c['c6']:.1f})")
        return ScoreResult(
            weighted_score=weighted, disposition=DISPOSITION_BDC,
            rationale=f"BDC+Databricks: {', '.join(reason_parts)}. Needs compute-scale or ML.",
            criteria_scores=c, triggered_rule="C5/C6-BDC",
        )

    # Default: SAC
    return ScoreResult(
        weighted_score=weighted, disposition=DISPOSITION_SAC,
        rationale=f"Default SAC path (weighted score {weighted:.2f}). Sanctioned SAP analytics platform.",
        criteria_scores=c, triggered_rule="default-SAC",
    )


def assert_report_disposition(
    report_uri: str,
    disposition: str,
    approver: str,
    weighted_score: float,
) -> str:
    """
    Write mig:approvedDisposition + score triples to the graph.
    Returns the report URI on success, or an error string.
    """
    disposition_map = {
        DISPOSITION_RETIRE: f"{MIG_BASE}Retire",
        DISPOSITION_NEXUS:  f"{MIG_BASE}ToNEXUS",
        DISPOSITION_SAC:    f"{MIG_BASE}ToSAC",
        DISPOSITION_BDC:    f"{MIG_BASE}ToBDCDatabricks",
    }
    disp_uri = disposition_map.get(disposition, f"{MIG_BASE}ToSAC")
    now      = datetime.now(timezone.utc).isoformat()

    sparql = f"""
PREFIX mig:  <{MIG_BASE}>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
INSERT DATA {{
    <{report_uri}> mig:approvedDisposition <{disp_uri}> .
    <{report_uri}> mig:dispositionScore    "{weighted_score:.3f}"^^xsd:decimal .
    <{report_uri}> mig:dispositionApprovedAt "{now}"^^xsd:dateTime .
    <{report_uri}> prov:wasAttributedTo    "{approver}" .
}}
"""
    try:
        from nexus.core.stardog_client import get_stardog
        get_stardog().update(sparql)
        return report_uri
    except Exception as exc:
        logger.error("assert_report_disposition failed: %s", exc)
        return f"Error: {exc}"


def ingest_report(report: dict) -> str:
    """
    Insert a mig:LegacyReport into the NEXUS graph from a dict (Tabular Editor export).

    Required keys: name, workspace
    Optional keys: info_provider, dax_measure_count, weekly_viewers,
                   c1..c10 scores, gxp, description
    Returns the asserted report URI.
    """
    # Build a deterministic URI from workspace + name
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", report.get("name", "unknown"))
    safe_ws   = re.sub(r"[^A-Za-z0-9_-]", "_", report.get("workspace", "default"))
    report_uri = f"https://ontology.ea.example.org/migration#{safe_ws}_{safe_name}"

    name        = report.get("name", "")
    workspace   = report.get("workspace", "")
    description = report.get("description", "")
    info_prov   = report.get("info_provider", "")
    dax_count   = int(report.get("dax_measure_count", 0))
    viewers     = int(report.get("weekly_viewers", 0))
    gxp         = bool(report.get("gxp", False))
    now         = datetime.now(timezone.utc).isoformat()

    # Build score triples if criteria are present
    score_triples = ""
    score_keys = [f"c{i}" for i in range(1, 11)]
    for k in score_keys:
        if k in report:
            score_triples += f'    <{report_uri}> mig:{k}Score "{float(report[k]):.1f}"^^xsd:decimal .\n'

    info_prov_triple = ""
    if info_prov:
        safe_ip = re.sub(r"[^A-Za-z0-9_-]", "_", info_prov)
        ip_uri  = f"https://ontology.ea.example.org/bw#{safe_ip}"
        info_prov_triple = f'    <{report_uri}> bw:sourceInfoProvider <{ip_uri}> .\n'

    sparql = f"""
PREFIX mig:  <{MIG_BASE}>
PREFIX bw:   <https://ontology.ea.example.org/bw#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
INSERT DATA {{
    <{report_uri}> a mig:LegacyReport ;
        rdfs:label "{name.replace('"', "'")}"{('@en' if name else '')} ;
        mig:workspace "{workspace.replace('"', "'")}" ;
        mig:daxMeasureCount {dax_count} ;
        mig:weeklyViewers   {viewers} ;
        mig:gxpStatus       "{str(gxp).lower()}"^^xsd:boolean ;
        mig:ingestedAt      "{now}"^^xsd:dateTime .
    {f'<{report_uri}> mig:reportDescription "{description.replace(chr(34), chr(39))}" .' if description else ''}
{info_prov_triple}{score_triples}}}
"""
    try:
        from nexus.core.stardog_client import get_stardog
        get_stardog().update(sparql)
        return report_uri
    except Exception as exc:
        logger.error("ingest_report failed for '%s': %s", name, exc)
        return f"Error: {exc}"
