"""Unit tests for core/apm_agent.py::_score_app — no external dependencies required."""
import pytest
from nexus.core.apm_agent import _score_app, TIMEClass


def _app(**kwargs):
    defaults = {
        "app": "urn:app:test",
        "appLabel": "TestApp",
        "ownerLabel": "alice",
        "lifecycle": "Active",
        "platform": "Azure",
        "domain": "Finance",
        "capCount": 3,
        "depCount": 2,
        "conCount": 4,
        "strategicIntent": "strategic",
    }
    defaults.update(kwargs)
    return defaults


# ── TIME quadrant correctness ─────────────────────────────────────────────────

def test_invest_quadrant():
    """High BV + high TF = Invest."""
    app = _app(capCount=5, conCount=10, lifecycle="Active", ownerLabel="alice")
    score = _score_app(app, findings=[], assets=[{"appLabel": "TestApp"}])
    assert score.time_class == TIMEClass.INVEST


def test_tolerate_quadrant():
    """Low BV + good tech = Tolerate."""
    app = _app(capCount=0, conCount=0, lifecycle="Active", ownerLabel="bob", strategicIntent="")
    score = _score_app(app, findings=[], assets=[])
    assert score.time_class == TIMEClass.TOLERATE


def test_migrate_quadrant():
    """High BV + bad lifecycle = Migrate."""
    app = _app(capCount=5, conCount=10, lifecycle="end-of-life", ownerLabel="carol")
    score = _score_app(app, findings=[], assets=[{"appLabel": "TestApp"}])
    assert score.time_class == TIMEClass.MIGRATE


def test_eliminate_quadrant():
    """Low BV + bad lifecycle + no owner = Eliminate."""
    app = _app(capCount=0, conCount=0, lifecycle="retired", ownerLabel="", strategicIntent="")
    score = _score_app(app, findings=[], assets=[])
    assert score.time_class == TIMEClass.ELIMINATE


def test_force_eliminate_on_high_risk_low_value():
    """risk >= 7 AND bv < 3 must force Eliminate even if TF is high."""
    critical_findings = [
        {"appLabel": "TestApp", "severity": "critical"},
        {"appLabel": "TestApp", "severity": "high"},
        {"appLabel": "TestApp", "severity": "critical"},
        {"appLabel": "TestApp", "severity": "high"},
    ]
    app = _app(capCount=0, conCount=0, lifecycle="Active", ownerLabel="", strategicIntent="")
    score = _score_app(app, findings=critical_findings, assets=[])
    assert score.time_class == TIMEClass.ELIMINATE


# ── Score bounds ──────────────────────────────────────────────────────────────

def test_portfolio_score_in_range():
    app = _app()
    score = _score_app(app, findings=[], assets=[])
    assert 0 <= score.portfolio_score <= 10


def test_all_dimension_scores_in_range():
    app = _app()
    score = _score_app(app, findings=[], assets=[])
    for dim in (score.business_value, score.technical_fit, score.risk_score, score.strategic_align):
        assert 0 <= dim <= 10


# ── Field mapping ─────────────────────────────────────────────────────────────

def test_label_and_owner_populated():
    app = _app(appLabel="MySAP", ownerLabel="david")
    score = _score_app(app, findings=[], assets=[])
    assert score.app_label == "MySAP"
    assert score.owner == "david"


def test_no_owner_increases_risk():
    with_owner    = _app(ownerLabel="alice")
    without_owner = _app(ownerLabel="")
    s1 = _score_app(with_owner,    findings=[], assets=[])
    s2 = _score_app(without_owner, findings=[], assets=[])
    assert s2.risk_score > s1.risk_score
