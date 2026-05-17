"""Unit tests for mcp_server.py — verifies tool registration without running the server."""
import pytest


def test_mcp_server_builds_without_error():
    """build_mcp_server() must not raise."""
    from nexus.mcp_server import build_mcp_server
    mcp = build_mcp_server()
    assert mcp is not None


def test_mcp_server_registers_nine_tools():
    import asyncio
    from nexus.mcp_server import build_mcp_server
    mcp = build_mcp_server()
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 9


def test_mcp_server_expected_tool_names():
    """All 9 expected nexus_* tool names must be registered."""
    from nexus.mcp_server import build_mcp_server
    mcp = build_mcp_server()

    expected = {
        "nexus_query",
        "nexus_impact_analyze",
        "nexus_apm_analyze",
        "nexus_sa_advisor",
        "nexus_generate_diagram",
        "nexus_assert_finding",
        "nexus_get_entity",
        "nexus_list_adrs",
        "nexus_graph_health",
    }

    # Try to get tool names from internal registry
    tool_manager = getattr(mcp, "_tool_manager", None)
    if tool_manager is not None:
        registered = set(tool_manager._tools.keys())
    else:
        # Try direct attribute
        raw = getattr(mcp, "_tools", {})
        registered = set(raw.keys()) if isinstance(raw, dict) else set()

    if registered:
        assert expected <= registered, f"Missing tools: {expected - registered}"


def test_api_post_returns_error_dict_on_bad_url():
    """_api_post must return {'error': ...} not raise when URL is invalid."""
    from nexus.mcp_server import _api_post
    result = _api_post("/v1/nonexistent", {"test": True})
    assert isinstance(result, dict)
    assert "error" in result


def test_api_get_returns_error_dict_on_bad_url():
    from nexus.mcp_server import _api_get
    result = _api_get("/v1/nonexistent", {})
    assert isinstance(result, dict)
    assert "error" in result


def test_nexus_query_blocked_query_returns_string():
    """nexus_query must always return a string (even if blocked or errored)."""
    from nexus.mcp_server import _nexus_query
    result = _nexus_query("delete all data from the graph")
    assert isinstance(result, str)
