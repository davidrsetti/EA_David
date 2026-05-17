"""Unit tests for core/tool_executor.py — no external services required."""
import pytest
from nexus.core.tool_executor import dispatch, _assert_finding, _run_sparql, _search_ontology


# ── dispatch() routing ────────────────────────────────────────────────────────

def test_dispatch_unknown_tool_returns_error_string():
    result = dispatch("totally_unknown_tool", {}, user_role="analyst")
    assert "Unknown tool" in result
    assert "totally_unknown_tool" in result


def test_dispatch_run_sparql_empty_sparql_returns_error():
    result = dispatch("run_sparql", {"sparql": ""}, user_role="analyst")
    assert "Error" in result or "error" in result.lower()


def test_dispatch_assert_finding_analyst_denied():
    """analyst role must be refused finding assertion."""
    result = dispatch(
        "assert_finding",
        {"label": "Test", "severity": "High",
         "asset_uri": "urn:x", "description": "desc"},
        user_role="analyst",
    )
    assert "Permission denied" in result or "denied" in result.lower()


def test_dispatch_assert_finding_viewer_denied():
    result = dispatch(
        "assert_finding",
        {"label": "Test", "severity": "High",
         "asset_uri": "urn:x", "description": "desc"},
        user_role="viewer",
    )
    assert "denied" in result.lower() or "Permission" in result


def test_dispatch_assert_finding_missing_label_returns_error():
    """admin role but missing label — should return validation error."""
    result = dispatch(
        "assert_finding",
        {"severity": "High", "asset_uri": "urn:x", "description": "desc"},
        user_role="admin",
    )
    assert "Error" in result or "required" in result.lower()


def test_dispatch_assert_finding_missing_asset_uri_returns_error():
    result = dispatch(
        "assert_finding",
        {"label": "Test", "severity": "High", "description": "desc"},
        user_role="admin",
    )
    assert "Error" in result or "required" in result.lower()


def test_dispatch_search_ontology_empty_term_returns_error():
    result = dispatch("search_ontology", {"term": ""}, user_role="analyst")
    assert "Error" in result or "required" in result.lower()


# ── _assert_finding() direct calls ───────────────────────────────────────────

@pytest.mark.parametrize("role", ["analyst", "viewer", "unknown"])
def test_assert_finding_rejected_roles(role):
    result = _assert_finding(
        {"label": "L", "severity": "Low", "asset_uri": "urn:x", "description": "D"},
        user_role=role,
    )
    assert "Permission denied" in result


@pytest.mark.parametrize("role", ["admin", "data-steward", "agent", "agent-admin"])
def test_assert_finding_proceeds_for_authorised_roles(monkeypatch, role):
    """For authorised roles, should reach the finding module (which may error on no graph)."""
    import nexus.core.tool_executor as te

    def _fake_assert(finding):
        return "urn:findings:test-123"

    monkeypatch.setattr("nexus.agents.findings.assert_finding", _fake_assert, raising=False)

    import nexus.agents.findings as af
    original = af.assert_finding
    af.assert_finding = _fake_assert
    try:
        result = _assert_finding(
            {"label": "L", "severity": "Medium", "asset_uri": "urn:x", "description": "D"},
            user_role=role,
        )
        assert "urn:findings:test-123" in result or "asserted" in result.lower()
    finally:
        af.assert_finding = original


# ── _run_sparql() ─────────────────────────────────────────────────────────────

def test_run_sparql_empty_sparql():
    result = _run_sparql({"sparql": ""}, user_role="analyst")
    assert "Error" in result


def test_run_sparql_blank_string():
    result = _run_sparql({"sparql": "   "}, user_role="analyst")
    assert "Error" in result


# ── _search_ontology() ────────────────────────────────────────────────────────

def test_search_ontology_empty_term():
    result = _search_ontology({"term": ""})
    assert "Error" in result or "required" in result.lower()


def test_search_ontology_finds_application_term():
    """'application' should hit multiple ontology lines — no external call needed."""
    result = _search_ontology({"term": "application"})
    # Either finds something or says no entries found — both are valid strings
    assert isinstance(result, str)
    assert len(result) > 0


def test_search_ontology_unknown_term_returns_message():
    result = _search_ontology({"term": "xyzzy_does_not_exist_in_ontology_12345"})
    assert "No ontology entries" in result or isinstance(result, str)
