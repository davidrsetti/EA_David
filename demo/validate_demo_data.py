#!/usr/bin/env python3
"""
demo/validate_demo_data.py — Pre-flight data validation for executive demo.

Run this 24h before the demo to confirm the graph has sufficient data
for each persona's questions. Exits 0 if all checks pass, 1 if any fail.

Usage:
    python demo/validate_demo_data.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHECKS = [
    # (label, SPARQL, minimum_count)
    (
        "Applications",
        "SELECT (COUNT(*) AS ?c) WHERE { ?s a app:Application }",
        10,
    ),
    (
        "Business Capabilities (L3)",
        "SELECT (COUNT(*) AS ?c) WHERE { ?s a ea:BusinessCapabilityL3 }",
        5,
    ),
    (
        "AI Agents",
        "SELECT (COUNT(*) AS ?c) WHERE { ?s a ai:Agent }",
        3,
    ),
    (
        "Open Findings",
        "SELECT (COUNT(*) AS ?c) WHERE { ?s a ops:AgentFinding }",
        1,
    ),
    (
        "ADRs",
        "SELECT (COUNT(*) AS ?c) WHERE { ?s a adv:ArchitectureDecisionRecord }",
        1,
    ),
    (
        "Data Assets",
        "SELECT (COUNT(*) AS ?c) WHERE { ?s a data:Dataset }",
        3,
    ),
    # Persona-specific: at least one ELIMINATE-class app for Exec Board question
    (
        "ELIMINATE-class apps (for Exec Board)",
        """SELECT (COUNT(*) AS ?c) WHERE {
            ?app a app:Application ;
                 app:lifecycle ?lc .
            FILTER(?lc IN ("retire","eol","sunset","legacy"))
        }""",
        1,
    ),
    # Capability gaps — unsupported capabilities for CDTO question
    (
        "Unsupported capabilities (capability gap)",
        """SELECT (COUNT(*) AS ?c) WHERE {
            ?cap a ea:BusinessCapabilityL3 .
            FILTER NOT EXISTS { ?app ea:enablesBusinessCapability ?cap }
        }""",
        1,
    ),
]


def run_checks() -> bool:
    from nexus.core.stardog_client import get_stardog

    try:
        db = get_stardog()
    except Exception as exc:
        print(f"FAIL  Cannot connect to StarDog: {exc}")
        return False

    all_ok = True
    print("\nNEXUS Demo Pre-flight Check")
    print("=" * 50)

    for label, sparql, minimum in CHECKS:
        try:
            _, rows = db.to_rows(db.query(sparql, inject_prefixes=True))
            count = int(rows[0].get("c", 0)) if rows else 0
            ok = count >= minimum
            status = "OK  " if ok else "FAIL"
            print(f"{status}  {label}: {count} (need >= {minimum})")
            if not ok:
                all_ok = False
        except Exception as exc:
            print(f"ERR   {label}: {exc}")
            all_ok = False

    print("=" * 50)
    if all_ok:
        print("All checks passed. Graph is demo-ready.")
    else:
        print("One or more checks failed. Load more data before the demo.")
    print()
    return all_ok


if __name__ == "__main__":
    ok = run_checks()
    sys.exit(0 if ok else 1)
