"""
core/claude_client.py — Anthropic Claude SDK singleton for NEXUS.

Provides:
  get_claude()        — cached Anthropic client
  tool_call_loop()    — multi-hop reasoning: Claude calls NEXUS tools until end_turn
  stream_answer()     — streaming text generator for SSE endpoints
  quick_complete()    — single-shot (no tools) completion with caching
"""
from __future__ import annotations

import json
import logging
from typing import Generator, Any

import anthropic

from nexus.config.settings import settings

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None

# NEXUS tool definitions exposed to Claude
NEXUS_TOOLS: list[dict] = [
    {
        "name": "run_sparql",
        "description": (
            "Execute a SPARQL SELECT query against the NEXUS enterprise knowledge graph. "
            "Use this to retrieve entity details, relationships, or aggregate counts when "
            "the initial result set needs enrichment or follow-up traversal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sparql": {
                    "type": "string",
                    "description": "A valid SPARQL SELECT statement with full PREFIX declarations."
                },
                "reason": {
                    "type": "string",
                    "description": "Why this follow-up query is needed to answer the question."
                },
            },
            "required": ["sparql"],
        },
    },
    {
        "name": "get_entity_context",
        "description": (
            "Fetch the full 2-hop context bundle for a named entity: properties, "
            "related entities, governance rules, and open findings. Use when you "
            "need richer detail about a specific application, capability, agent, or dataset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "The name or label of the entity (application, capability, etc.)."
                },
            },
            "required": ["entity_name"],
        },
    },
    {
        "name": "assert_finding",
        "description": (
            "Record an architectural finding or risk to the NEXUS knowledge graph. "
            "Use this when your analysis reveals a genuine risk, gap, or governance issue "
            "that should be tracked. Do NOT assert trivial or obvious findings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label":       {"type": "string", "description": "Short descriptive label for the finding."},
                "severity":    {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
                "asset_uri":   {"type": "string", "description": "URI of the affected asset in the knowledge graph."},
                "description": {"type": "string", "description": "Full description of the finding and its impact."},
            },
            "required": ["label", "severity", "asset_uri", "description"],
        },
    },
    {
        "name": "search_ontology",
        "description": (
            "Search the live ontology for class or property definitions matching a term. "
            "Use this when you are unsure which ontology term to use in a SPARQL query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "The concept to look up (e.g. 'data product', 'capability', 'agent')."
                },
            },
            "required": ["term"],
        },
    },
]


def get_claude() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic.api_key)
    return _client


def _make_system_blocks(system_text: str) -> list[dict]:
    """Wrap system text, caching the whole block if enabled."""
    block: dict[str, Any] = {"type": "text", "text": system_text}
    if settings.anthropic.enable_cache:
        block["cache_control"] = {"type": "ephemeral"}
    return [block]


def tool_call_loop(
    question: str,
    result_rows: list[dict],
    columns: list[str],
    sparql: str,
    total_count: int,
    system_prompt: str,
    tool_executor: Any,       # callable: (name, input, **kw) -> str
    user_role: str = "analyst",
    session_id: str = "",
    max_iterations: int = 6,
) -> tuple[str, list[str]]:
    """
    Run a multi-hop Claude reasoning loop with tool_use.

    Claude sees the initial SPARQL result and can issue follow-up tool calls
    (run_sparql, get_entity_context, assert_finding, search_ontology) until
    it reaches end_turn with a final text answer.

    Returns:
        (answer_text, suggestions)  — formatted answer + 3 follow-up question suggestions
    """
    client = get_claude()
    preview = json.dumps(result_rows[:30], indent=2)
    shown   = min(30, len(result_rows))

    user_content = (
        f"Question: {question}\n\n"
        f"Initial SPARQL: {sparql}\n\n"
        f"Result columns: {', '.join(columns)}\n"
        f"Total results: {total_count} (showing first {shown})\n\n"
        f"Results:\n{preview}"
    )

    messages: list[dict] = [{"role": "user", "content": user_content}]
    answer   = ""
    itr      = 0

    while itr < max_iterations:
        itr += 1
        try:
            response = client.messages.create(
                model     = settings.anthropic.answer_model,
                max_tokens= settings.anthropic.max_tokens,
                system    = _make_system_blocks(system_prompt),
                tools     = NEXUS_TOOLS,
                messages  = messages,
            )
        except Exception as exc:
            logger.error("Claude tool_call_loop error (iter %d): %s", itr, exc)
            break

        # Collect assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract final text
            for block in response.content:
                if hasattr(block, "text"):
                    answer += block.text
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    result_str = tool_executor(
                        block.name,
                        block.input,
                        user_role=user_role,
                        session_id=session_id,
                    )
                except Exception as exc:
                    result_str = f"Tool error: {exc}"
                    logger.warning("tool_executor('%s') failed: %s", block.name, exc)

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     str(result_str),
                })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop_reason
        logger.warning("Unexpected stop_reason: %s", response.stop_reason)
        break

    # Ask Claude for follow-up suggestions (cheap, cached call)
    suggestions: list[str] = []
    try:
        sug_resp = client.messages.create(
            model      = settings.anthropic.answer_model,
            max_tokens = 300,
            system     = _make_system_blocks(
                "Given the enterprise KG question and answer, suggest exactly 3 concise "
                "follow-up questions the user might want to ask next. Return ONLY a JSON "
                'array of 3 strings, e.g. ["Q1?","Q2?","Q3?"]. No preamble.'
            ),
            messages   = [{
                "role": "user",
                "content": f"Original question: {question}\nAnswer summary: {answer[:300]}"
            }],
        )
        raw_sug = ""
        for block in sug_resp.content:
            if hasattr(block, "text"):
                raw_sug += block.text
        import re as _re
        m = _re.search(r"\[.*\]", raw_sug, _re.DOTALL)
        if m:
            suggestions = json.loads(m.group())[:3]
    except Exception:
        pass

    return answer.strip(), suggestions


def stream_answer(
    system_prompt: str,
    user_message: str,
) -> Generator[str, None, None]:
    """
    Yield streamed text tokens from Claude (no tool use — for SSE streaming endpoint).
    """
    client = get_claude()
    try:
        with client.messages.stream(
            model      = settings.anthropic.answer_model,
            max_tokens = settings.anthropic.max_tokens,
            system     = _make_system_blocks(system_prompt),
            messages   = [{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as exc:
        logger.error("stream_answer error: %s", exc)
        yield f"\n[Stream error: {exc}]"


def quick_complete(system_prompt: str, user_message: str, max_tokens: int = 1000) -> str:
    """Single-shot Claude completion with prompt caching. No tools."""
    client = get_claude()
    try:
        resp = client.messages.create(
            model      = settings.anthropic.answer_model,
            max_tokens = max_tokens,
            system     = _make_system_blocks(system_prompt),
            messages   = [{"role": "user", "content": user_message}],
        )
        text = ""
        for block in resp.content:
            if hasattr(block, "text"):
                text += block.text
        return text.strip()
    except Exception as exc:
        logger.error("quick_complete error: %s", exc)
        return ""
