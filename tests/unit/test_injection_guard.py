"""Unit tests for the SPARQL injection guard in api/main.py."""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException
from nexus.api.main import _safe_filter_param


# ── _safe_filter_param ────────────────────────────────────────────────────────

@pytest.mark.parametrize("malicious", [
    "finance}",
    "{injected",
    "hr#comment",
    "domain;DROP",
    "ok}bad",
    ";",
    "{}",
    "normal#",
])
def test_safe_filter_rejects_injection_chars(malicious):
    with pytest.raises(HTTPException) as exc_info:
        _safe_filter_param(malicious, "focus_domain")
    assert exc_info.value.status_code == 422


@pytest.mark.parametrize("safe", [
    "",
    "finance",
    "Human Resources",
    "IT & Operations",
    "domain-name",
    "domain_name",
    "CamelCase",
    "My App v2.1",
])
def test_safe_filter_accepts_clean_values(safe):
    result = _safe_filter_param(safe, "focus_domain")
    assert result == safe
