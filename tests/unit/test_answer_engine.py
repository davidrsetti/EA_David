"""Unit tests for core/answer_engine.py — no LLM calls required."""
import pytest
from nexus.core.answer_engine import AnswerResult, synthesise_full, synthesise


# ── AnswerResult dataclass ────────────────────────────────────────────────────

def test_answer_result_construction():
    r = AnswerResult(
        answer="42 apps found.",
        sparql="SELECT * WHERE { ?s a app:Application }",
        columns=["app", "label"],
        rows=[{"app": "urn:x", "label": "SAP"}],
        row_count=1,
        error=None,
    )
    assert r.answer == "42 apps found."
    assert r.row_count == 1
    assert r.suggestions == []
    assert r.pii_detected is False
    assert r.redacted is False


def test_answer_result_suggestions_default_empty():
    r = AnswerResult(answer="a", sparql="", columns=[], rows=[], row_count=0, error=None)
    assert isinstance(r.suggestions, list)
    assert len(r.suggestions) == 0


def test_answer_result_with_suggestions():
    r = AnswerResult(
        answer="a", sparql="", columns=[], rows=[], row_count=0, error=None,
        suggestions=["Q1?", "Q2?", "Q3?"],
    )
    assert len(r.suggestions) == 3


# ── Empty-rows fast path (no LLM call) ───────────────────────────────────────

def test_synthesise_full_empty_rows_returns_no_results_answer():
    result = synthesise_full(
        question="Which apps support Order-to-Cash?",
        columns=["app", "label"],
        rows=[],
        sparql="SELECT * WHERE { ?s a app:Application }",
        total_count=0,
    )
    assert isinstance(result, AnswerResult)
    assert "No results" in result.answer or "no results" in result.answer.lower()
    assert result.row_count == 0
    assert result.error is None


def test_synthesise_full_empty_rows_suggestions_empty():
    result = synthesise_full(
        question="Which apps support Order-to-Cash?",
        columns=[],
        rows=[],
        sparql="SELECT * WHERE { ?s a app:Application }",
        total_count=0,
    )
    assert result.suggestions == []


def test_synthesise_full_empty_rows_contains_caveat_section():
    result = synthesise_full(
        question="How many AI agents exist?",
        columns=[],
        rows=[],
        sparql="SELECT * WHERE { ?s a ai:Agent }",
        total_count=0,
    )
    assert "Confidence" in result.answer or "caveat" in result.answer.lower()


def test_synthesise_wraps_synthesise_full_and_returns_string():
    """synthesise() must return a plain string (backward-compat wrapper)."""
    result = synthesise(
        question="Test question",
        columns=[],
        rows=[],
        sparql="SELECT * WHERE { ?s ?p ?o }",
        total_count=0,
    )
    assert isinstance(result, str)
    assert len(result) > 0


# ── GPT-4o error fallback ─────────────────────────────────────────────────────

def test_synthesise_openai_error_returns_fallback_answer(monkeypatch):
    """When OpenAI fails, _synthesise_openai returns a graceful fallback."""
    from nexus.core import answer_engine

    def _bad_client():
        raise RuntimeError("No API key in test")

    monkeypatch.setattr(answer_engine, "_openai_client", _bad_client)

    result = answer_engine._synthesise_openai(
        question="Test?",
        columns=["col"],
        rows=[{"col": "val"}],
        sparql="SELECT * WHERE { ?s ?p ?o }",
        total_count=1,
    )
    assert isinstance(result, AnswerResult)
    assert result.error is not None
    assert "Direct Answer" in result.answer
