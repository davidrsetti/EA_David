"""Unit tests for nl_to_sparql helper functions — no external dependencies."""
import pytest
from nexus.core.nl_to_sparql import _sanitise, _inject_missing_prefixes


# ── _sanitise ─────────────────────────────────────────────────────────────────

def test_sanitise_strips_markdown_fences():
    raw = "```sparql\nSELECT * WHERE { ?s ?p ?o }\n```"
    assert _sanitise(raw) == "SELECT * WHERE { ?s ?p ?o }"


def test_sanitise_extracts_from_prefix_keyword():
    raw = "Here is your query:\nPREFIX ex: <http://example.com/>\nSELECT ?s WHERE { ?s a ex:Foo }"
    result = _sanitise(raw)
    assert result.startswith("PREFIX ex:")


def test_sanitise_handles_list_string():
    raw = "['SELECT * WHERE { ?s ?p ?o }']"
    assert _sanitise(raw) == "SELECT * WHERE { ?s ?p ?o }"


def test_sanitise_returns_stripped_plain_query():
    raw = "  SELECT * WHERE { ?s ?p ?o }  "
    assert _sanitise(raw) == "SELECT * WHERE { ?s ?p ?o }"


def test_sanitise_handles_ask_query():
    raw = "```\nASK { <urn:x> a <urn:y> }\n```"
    assert _sanitise(raw) == "ASK { <urn:x> a <urn:y> }"


# ── _inject_missing_prefixes ──────────────────────────────────────────────────

def test_inject_adds_missing_prefix():
    query = "SELECT ?s WHERE { ?s a app:Application }"
    result = _inject_missing_prefixes(query)
    assert "PREFIX app:" in result


def test_inject_does_not_duplicate_existing_prefix():
    query = "PREFIX app: <http://example.com/app#>\nSELECT ?s WHERE { ?s a app:Application }"
    result = _inject_missing_prefixes(query)
    assert result.count("PREFIX app:") == 1


def test_inject_skips_unknown_prefix():
    query = "SELECT ?s WHERE { ?s a zz:Unknown }"
    result = _inject_missing_prefixes(query)
    assert "PREFIX zz:" not in result


def test_inject_leaves_full_iri_untouched():
    query = "SELECT ?s WHERE { ?s a <http://example.com/Foo> }"
    result = _inject_missing_prefixes(query)
    assert result == query


def test_inject_skips_http_as_prefix():
    query = "SELECT ?s WHERE { ?s <http://schema.org/name> ?n }"
    result = _inject_missing_prefixes(query)
    assert "PREFIX http:" not in result
