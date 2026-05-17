"""Unit tests for core/report_scorer.py — no external services required."""
import pytest
from nexus.core.report_scorer import (
    score_report, ScoreResult,
    DISPOSITION_RETIRE, DISPOSITION_NEXUS, DISPOSITION_SAC, DISPOSITION_BDC,
)


def _scores(**kwargs) -> dict:
    """Build a scores dict with defaults 0 except overrides."""
    base = {f"c{i}": 0.0 for i in range(1, 11) if i != 9}
    base.update(kwargs)
    return base


# ── GxP override ──────────────────────────────────────────────────────────────

def test_gxp_override_routes_to_sac():
    result = score_report(_scores(c1=5, c2=5), gxp=True)
    assert result.disposition == DISPOSITION_SAC
    assert result.triggered_rule == "C9-GxP"


# ── Retire rule ───────────────────────────────────────────────────────────────

def test_no_usage_and_duplicated_routes_to_retire():
    result = score_report(_scores(c2=0.0, c3=5.0))
    assert result.disposition == DISPOSITION_RETIRE
    assert result.triggered_rule == "C2+C3-Retire"


def test_low_usage_but_not_duplicated_does_not_retire():
    result = score_report(_scores(c2=0.0, c3=2.0))
    assert result.disposition != DISPOSITION_RETIRE


# ── NEXUS rule ────────────────────────────────────────────────────────────────

def test_high_nexus_alignment_routes_to_nexus():
    result = score_report(_scores(c10=4.5, c7=4.5, c6=2.0))
    assert result.disposition == DISPOSITION_NEXUS
    assert result.triggered_rule == "C10+C7+C6-NEXUS"


def test_nexus_rule_blocked_by_high_volume():
    """C6 > 3 blocks the NEXUS rule → falls through to SAC or BDC."""
    result = score_report(_scores(c10=5.0, c7=5.0, c6=4.0))
    assert result.disposition != DISPOSITION_NEXUS


# ── SAC rule ─────────────────────────────────────────────────────────────────

def test_exec_sap_source_dashboard_routes_to_sac():
    result = score_report(_scores(c8=4.5, c4=4.0, c7=2.0))
    assert result.disposition == DISPOSITION_SAC
    assert result.triggered_rule in ("C8+C4+C7-SAC", "default-SAC")


# ── BDC rule ─────────────────────────────────────────────────────────────────

def test_high_logic_complexity_routes_to_bdc():
    result = score_report(_scores(c5=5.0))
    assert result.disposition == DISPOSITION_BDC
    assert result.triggered_rule == "C5/C6-BDC"


def test_large_volume_routes_to_bdc():
    result = score_report(_scores(c6=4.5))
    assert result.disposition == DISPOSITION_BDC


# ── Default route ─────────────────────────────────────────────────────────────

def test_all_zeros_routes_to_sac_default():
    result = score_report(_scores())
    assert result.disposition == DISPOSITION_SAC
    assert result.triggered_rule == "default-SAC"


# ── Return type ───────────────────────────────────────────────────────────────

def test_score_report_returns_score_result():
    result = score_report(_scores(c1=3, c2=2, c4=4, c7=5, c10=4))
    assert isinstance(result, ScoreResult)
    assert 0.0 <= result.weighted_score <= 5.0
    assert isinstance(result.rationale, str)
    assert len(result.rationale) > 0


def test_criteria_scores_in_result():
    scores = _scores(c1=3.5, c2=4.0)
    result = score_report(scores)
    assert result.criteria_scores["c1"] == 3.5
    assert result.criteria_scores["c2"] == 4.0


# ── Weighted score calculation ────────────────────────────────────────────────

def test_all_fives_gives_max_score():
    result = score_report({f"c{i}": 5.0 for i in range(1, 11) if i != 9})
    assert abs(result.weighted_score - 5.0) < 0.01


def test_all_zeros_gives_min_score():
    result = score_report(_scores())
    assert abs(result.weighted_score - 0.0) < 0.01
