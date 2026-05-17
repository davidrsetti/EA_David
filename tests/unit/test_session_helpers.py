"""Unit tests for agents/session.py helper functions — no graph connection required."""
import pytest
from nexus.agents.session import _esc


# ── _esc() ────────────────────────────────────────────────────────────────────

def test_esc_empty_string():
    assert _esc("") == ""


def test_esc_plain_string_unchanged():
    assert _esc("hello world") == "hello world"


def test_esc_escapes_double_quotes():
    assert _esc('say "hello"') == 'say \\"hello\\"'


def test_esc_escapes_backslash():
    assert _esc("C:\\Users\\david") == "C:\\\\Users\\\\david"


def test_esc_escapes_both():
    assert _esc('path "C:\\dir"') == 'path \\"C:\\\\dir\\"'


def test_esc_newline_preserved():
    """Newlines are not escaped by _esc (only quotes and backslashes)."""
    s = "line1\nline2"
    assert _esc(s) == s


def test_esc_unicode_preserved():
    s = "café ☕"
    assert _esc(s) == s


def test_esc_multiple_quotes():
    assert _esc('a "b" "c"') == 'a \\"b\\" \\"c\\"'
