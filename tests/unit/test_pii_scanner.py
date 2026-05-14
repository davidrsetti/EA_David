"""Unit tests for audit/pii_scanner.py — no external dependencies required."""
import pytest
from nexus.audit.pii_scanner import scan_and_redact, ScanResult


def _rows(*dicts):
    return list(dicts)


def test_empty_rows_returns_clean_result():
    result = scan_and_redact([])
    assert result.pii_found is False
    assert result.detections == []
    assert result.redacted_rows == []


def test_email_detected_and_redacted():
    rows = _rows({"name": "Alice", "contact": "alice@example.com"})
    result = scan_and_redact(rows, redact=True)
    assert result.pii_found is True
    assert any(d["type"] == "email" for d in result.detections)
    assert "[REDACTED]" in result.redacted_rows[0]["contact"]


def test_us_ssn_detected_and_redacted():
    rows = _rows({"id": "123-45-6789", "name": "Bob"})
    result = scan_and_redact(rows, redact=True)
    assert result.pii_found is True
    assert any(d["type"] == "us_ssn" for d in result.detections)
    assert "[REDACTED]" in result.redacted_rows[0]["id"]


def test_uk_nino_detected():
    rows = _rows({"nino": "AB123456C"})
    result = scan_and_redact(rows, redact=True)
    assert result.pii_found is True
    assert any(d["type"] == "uk_nino" for d in result.detections)


def test_no_pii_row_passes_through_unchanged():
    rows = _rows({"app": "SAP ERP", "lifecycle": "Active"})
    result = scan_and_redact(rows, redact=True)
    assert result.pii_found is False
    assert result.redacted_rows[0]["app"] == "SAP ERP"


def test_redact_false_preserves_original_value():
    rows = _rows({"email": "test@corp.com"})
    result = scan_and_redact(rows, redact=False)
    assert result.pii_found is True
    assert result.redacted_rows[0]["email"] == "test@corp.com"


def test_detection_count_increments_per_row():
    rows = _rows(
        {"contact": "a@b.com"},
        {"contact": "c@d.com"},
    )
    result = scan_and_redact(rows, redact=True)
    email_det = next(d for d in result.detections if d["type"] == "email")
    assert email_det["count"] == 2


def test_none_value_does_not_crash():
    rows = _rows({"field": None})
    result = scan_and_redact(rows, redact=True)
    assert result.pii_found is False
