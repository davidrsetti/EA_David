"""
core/answer_engine.py — Synthesises SPARQL results into structured NL answers.

Uses Claude claude-sonnet-4-6 with tool_use for multi-hop graph reasoning
when ANTHROPIC_API_KEY is configured. Falls back to GPT-4o otherwise.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field

from nexus.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AnswerResult:
    answer:       str
    sparql:       str
    columns:      list[str]
    rows:         list[dict]
    row_count:    int
    error:        str | None
    pii_detected: bool = False
    redacted:     bool = False
    suggestions:  list[str] = field(default_factory=list)


SYSTEM_PROMPT = """You are NEXUS, a precise enterprise knowledge graph assistant.

You have access to tools to perform follow-up SPARQL queries, fetch entity context,
and assert findings. Use them when the initial results are incomplete or ambiguous.
Limit yourself to at most 4 tool calls per question.

After gathering all needed information, structure your final response in EXACTLY
THREE sections using these headers:

**Direct Answer**
Clear, concise answer in plain English. Highlight key entities, counts, and relationships.
Use bullet points for lists of 4 or more items.

**Reasoning & Explanation**
Explain which parts of the enterprise knowledge model were traversed.
Call out notable patterns, relationships, or gaps (e.g. missing stewards, orphaned apps).
If the result implies a risk or compliance concern, say so plainly.

**Confidence & Caveats**
State your confidence (High / Medium / Low).
Note assumptions, empty OPTIONAL fields, partial data coverage, or incomplete results.
If the result is complete and unambiguous, state that clearly.

Write professional, direct prose. Do NOT mention SPARQL or graph internals
unless explicitly asked. Numbers and entity names must be precise."""


def synthesise(
    question: str,
    columns:  list[str],
    rows:     list[dict],
    sparql:   str,
    total_count: int,
    user_role:   str = "analyst",
    session_id:  str = "",
) -> str:
    """
    Generate a structured NL answer from SPARQL results.
    Returns the formatted answer string.
    Callers that want suggestions should use synthesise_full().
    """
    result = synthesise_full(question, columns, rows, sparql, total_count, user_role, session_id)
    return result.answer


def synthesise_full(
    question:    str,
    columns:     list[str],
    rows:        list[dict],
    sparql:      str,
    total_count: int,
    user_role:   str = "analyst",
    session_id:  str = "",
) -> AnswerResult:
    """
    Full synthesis returning AnswerResult with answer + suggestions.
    Uses Claude tool_use if available, falls back to GPT-4o.
    """
    if not rows:
        answer = (
            "**Direct Answer**\n"
            f"No results were found for: _{question}_\n\n"
            "**Reasoning & Explanation**\n"
            "The query executed successfully but returned zero matching records. "
            "This could mean: the entities don't exist in the graph yet, the relationships "
            "are modelled differently, or the data has not been synchronised from the source system.\n\n"
            "**Confidence & Caveats**\n"
            "High confidence that the query is correct; low confidence that 'no data' is the "
            "true answer — it may reflect incomplete graph coverage. "
            "Consider checking the source system directly or reviewing the ontology mappings."
        )
        return AnswerResult(
            answer=answer, sparql=sparql, columns=columns,
            rows=rows, row_count=0, error=None,
        )

    if settings.anthropic.enabled:
        return _synthesise_claude(question, columns, rows, sparql, total_count, user_role, session_id)
    return _synthesise_openai(question, columns, rows, sparql, total_count)


# ── Claude path (multi-hop tool_use) ───────────────────────────────────

def _synthesise_claude(
    question:    str,
    columns:     list[str],
    rows:        list[dict],
    sparql:      str,
    total_count: int,
    user_role:   str,
    session_id:  str,
) -> AnswerResult:
    from nexus.core.claude_client  import tool_call_loop
    from nexus.core.tool_executor  import dispatch

    try:
        answer, suggestions = tool_call_loop(
            question     = question,
            result_rows  = rows,
            columns      = columns,
            sparql       = sparql,
            total_count  = total_count,
            system_prompt= SYSTEM_PROMPT,
            tool_executor= dispatch,
            user_role    = user_role,
            session_id   = session_id,
        )
        if not answer:
            raise ValueError("Empty response from Claude")
        return AnswerResult(
            answer=answer, sparql=sparql, columns=columns,
            rows=rows, row_count=len(rows), error=None,
            suggestions=suggestions,
        )
    except Exception as exc:
        logger.warning("Claude synthesis failed (%s), falling back to GPT-4o", exc)
        return _synthesise_openai(question, columns, rows, sparql, total_count)


# ── GPT-4o fallback path ────────────────────────────────────────────────

_COMPLETION_TOKEN_MODELS = {"o3-mini", "o3", "o1", "o1-mini", "o1-preview"}

_OAI_SYSTEM = """You are NEXUS, a precise enterprise knowledge graph assistant.
Answer the user's question using the SPARQL results provided.
Structure your response in EXACTLY THREE sections:

**Direct Answer**  **Reasoning & Explanation**  **Confidence & Caveats**

Write in professional, direct prose. Numbers and entity names must be precise."""


def _openai_client():
    from openai import OpenAI
    return OpenAI(api_key=settings.openai.api_key)


def _token_param(model: str, n: int) -> dict:
    key = "max_completion_tokens" if model in _COMPLETION_TOKEN_MODELS else "max_tokens"
    return {key: n}


def _synthesise_openai(
    question:    str,
    columns:     list[str],
    rows:        list[dict],
    sparql:      str,
    total_count: int,
) -> AnswerResult:
    preview = json.dumps(rows[:30], indent=2)
    shown   = min(30, len(rows))
    model   = settings.openai.answer_model

    try:
        resp = _openai_client().chat.completions.create(
            model    = model,
            messages = [
                {"role": "system", "content": _OAI_SYSTEM},
                {"role": "user",   "content": (
                    f"Question: {question}\n\n"
                    f"Result columns: {', '.join(columns)}\n"
                    f"Total results: {total_count} (showing first {shown})\n\n"
                    f"Results:\n{preview}"
                )},
            ],
            temperature = 0.2,
            **_token_param(model, settings.openai.max_tokens),
        )
        c = resp.choices[0].message.content or ""
        if isinstance(c, list):
            c = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
        return AnswerResult(
            answer=c.strip(), sparql=sparql, columns=columns,
            rows=rows, row_count=len(rows), error=None,
        )
    except Exception as exc:
        logger.error("GPT-4o synthesis failed: %s", exc)
        return AnswerResult(
            answer=(
                f"**Direct Answer**\nFound {total_count} result(s).\n\n"
                f"**Reasoning & Explanation**\nColumns: {', '.join(columns)}. "
                f"Synthesis model unavailable.\n\n"
                f"**Confidence & Caveats**\nData is accurate; narrative unavailable: {exc}"
            ),
            sparql=sparql, columns=columns, rows=rows,
            row_count=len(rows), error=str(exc),
        )
