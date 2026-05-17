"""Unit tests for core/claude_client.py — no Anthropic API calls required."""
import pytest
from nexus.core.claude_client import _make_system_blocks, NEXUS_TOOLS


# ── NEXUS_TOOLS definition ────────────────────────────────────────────────────

def test_nexus_tools_count():
    assert len(NEXUS_TOOLS) == 5


def test_nexus_tools_names():
    names = {t["name"] for t in NEXUS_TOOLS}
    assert names == {"run_sparql", "get_entity_context", "assert_finding", "search_ontology", "query_databricks"}


def test_nexus_tools_all_have_input_schema():
    for tool in NEXUS_TOOLS:
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


def test_nexus_tools_all_have_description():
    for tool in NEXUS_TOOLS:
        assert "description" in tool
        assert len(tool["description"]) > 10


def test_run_sparql_tool_requires_sparql():
    tool = next(t for t in NEXUS_TOOLS if t["name"] == "run_sparql")
    assert "sparql" in tool["input_schema"]["required"]


def test_assert_finding_tool_requires_all_fields():
    tool = next(t for t in NEXUS_TOOLS if t["name"] == "assert_finding")
    required = set(tool["input_schema"]["required"])
    assert required == {"label", "severity", "asset_uri", "description"}


def test_assert_finding_severity_is_enum():
    tool = next(t for t in NEXUS_TOOLS if t["name"] == "assert_finding")
    severity_props = tool["input_schema"]["properties"]["severity"]
    assert "enum" in severity_props
    assert set(severity_props["enum"]) == {"Low", "Medium", "High", "Critical"}


# ── _make_system_blocks() ─────────────────────────────────────────────────────

def test_make_system_blocks_returns_list():
    blocks = _make_system_blocks("Hello NEXUS")
    assert isinstance(blocks, list)
    assert len(blocks) == 1


def test_make_system_blocks_contains_text():
    blocks = _make_system_blocks("Hello NEXUS")
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "Hello NEXUS"


def test_make_system_blocks_with_cache_enabled():
    """When the module-level settings have cache enabled (default), cache_control is present."""
    import nexus.core.claude_client as cc
    from nexus.config.settings import AnthropicSettings

    class _FakeSettings:
        class anthropic:
            enable_cache = True

    orig = cc.settings
    cc.settings = _FakeSettings()
    try:
        blocks = cc._make_system_blocks("test with cache")
        assert "cache_control" in blocks[0]
        assert blocks[0]["cache_control"]["type"] == "ephemeral"
    finally:
        cc.settings = orig


def test_make_system_blocks_without_cache(monkeypatch):
    from nexus.config import settings as _cfg
    from nexus.config.settings import AnthropicSettings
    # Create a settings override with cache disabled
    orig = _cfg.settings
    try:
        import nexus.core.claude_client as cc
        # Patch settings on the claude_client module directly
        class _FakeAnthropic:
            api_key = "sk-ant-test"
            enable_cache = False
            answer_model = "claude-sonnet-4-6"
            max_tokens = 1000
        class _FakeSettings:
            anthropic = _FakeAnthropic()
        cc.settings = _FakeSettings()
        blocks = cc._make_system_blocks("no cache test")
        assert "cache_control" not in blocks[0]
    finally:
        cc.settings = orig
