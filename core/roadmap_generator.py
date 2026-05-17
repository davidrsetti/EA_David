"""core/roadmap_generator.py — Claude-driven phased roadmap from gap analysis."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from nexus.core.claude_client import quick_complete
from nexus.core.gap_analyzer import GapAnalysis

logger = logging.getLogger(__name__)


@dataclass
class Initiative:
    title: str
    description: str
    priority: str
    phase: int
    effort: str
    gap_categories: list[str]
    kpis: list[str]


@dataclass
class Roadmap:
    generated_at: str
    horizon_months: int
    total_initiatives: int
    phases: dict[int, list[Initiative]]
    executive_summary: str
    constraints: str


def _fallback_roadmap(horizon_months: int, constraints: str) -> Roadmap:
    initiative = Initiative(
        title="Address Identified Gaps",
        description="Review the gap analysis findings and prioritise remediation efforts.",
        priority="P1",
        phase=1,
        effort="4-6 weeks",
        gap_categories=[],
        kpis=[],
    )
    return Roadmap(
        generated_at=datetime.now(timezone.utc).isoformat(),
        horizon_months=horizon_months,
        total_initiatives=1,
        phases={1: [initiative]},
        executive_summary="Roadmap generation encountered an error. Manual review of gap findings is recommended.",
        constraints=constraints,
    )


def generate_roadmap(
    gap_analysis: GapAnalysis,
    horizon_months: int = 18,
    constraints: str = "",
) -> Roadmap:
    top_gaps_by_cat: dict[str, list[str]] = {}
    for g in gap_analysis.gaps:
        top_gaps_by_cat.setdefault(g.category, [])
        if len(top_gaps_by_cat[g.category]) < 3:
            top_gaps_by_cat[g.category].append(g.label)

    constraint_block = f"\nConstraints: {constraints}" if constraints else ""

    prompt = f"""You are an enterprise architect generating a phased IT roadmap.

Gap analysis summary: {gap_analysis.summary}
Total gaps: {gap_analysis.total_gaps}
Gaps by category: {gap_analysis.by_category}
Top gap examples: {top_gaps_by_cat}
Roadmap horizon: {horizon_months} months{constraint_block}

Return ONLY valid JSON in this exact structure (no markdown, no commentary):
{{
  "executive_summary": "2-3 sentence executive summary",
  "phases": {{
    "1": [
      {{
        "title": "Initiative title",
        "description": "What will be done and why",
        "priority": "P1",
        "effort": "4-6 weeks",
        "gap_categories": ["capability"],
        "kpis": ["Reduced uncovered capabilities"]
      }}
    ],
    "2": [],
    "3": []
  }}
}}

Rules:
- Phase 1 = immediate (0-6 months), Phase 2 = medium (6-12 months), Phase 3 = long (12+ months)
- Priority: P1 for High severity gaps, P2 for Medium, P3 for Low
- Include 2-4 initiatives per phase
- Map each initiative to the gap categories it addresses"""

    resp = quick_complete(
        "You are an enterprise architect. Return only valid JSON. No preamble, no markdown.",
        prompt,
        max_tokens=2000,
    )

    if not resp:
        logger.warning("roadmap_generator: Claude returned empty response, using fallback")
        return _fallback_roadmap(horizon_months, constraints)

    match = re.search(r'\{.*\}', resp, re.DOTALL)
    if not match:
        logger.warning("roadmap_generator: no JSON found in Claude response")
        return _fallback_roadmap(horizon_months, constraints)

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.warning("roadmap_generator: JSON parse error: %s", exc)
        return _fallback_roadmap(horizon_months, constraints)

    phases: dict[int, list[Initiative]] = {}
    raw_phases = data.get("phases", {})
    total = 0
    for phase_key, initiative_list in raw_phases.items():
        phase_num = int(phase_key)
        phase_initiatives = []
        for raw in (initiative_list or []):
            ini = Initiative(
                title=raw.get("title", "Untitled"),
                description=raw.get("description", ""),
                priority=raw.get("priority", "P2"),
                phase=phase_num,
                effort=raw.get("effort", "TBD"),
                gap_categories=raw.get("gap_categories", []),
                kpis=raw.get("kpis", []),
            )
            phase_initiatives.append(ini)
            total += 1
        phases[phase_num] = phase_initiatives

    if not phases:
        return _fallback_roadmap(horizon_months, constraints)

    return Roadmap(
        generated_at=datetime.now(timezone.utc).isoformat(),
        horizon_months=horizon_months,
        total_initiatives=total,
        phases=phases,
        executive_summary=data.get("executive_summary", ""),
        constraints=constraints,
    )
