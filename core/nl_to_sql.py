"""
core/nl_to_sql.py — Natural language → Databricks SQL pipeline.

Schema context comes from UC metadata in StarDog (catalog/schema/table/columns).
Supports multiple tables scoped by Business Unit + Data Domain.
"""
from __future__ import annotations

import logging
import re

from nexus.config.settings import settings
from nexus.core.nl_to_sparql import _chat_completion, _content

logger = logging.getLogger(__name__)

_FORBIDDEN = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|UPDATE|INSERT|ALTER|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

# Max columns per table injected into the prompt (keeps token count manageable)
_MAX_COLS_PER_TABLE = 60


def nl_to_sql(
    question: str,
    tables: list[dict],
    bu_context: str = "",
    domain_context: list[str] | None = None,
) -> str:
    """
    Translate a natural language question to a Databricks SQL query.

    Args:
        question:       The user's question in plain English.
        tables:         List of table dicts, each with keys:
                          catalog, schema, table,
                          columns: [{colName, dataType, ordinalPosition, isNullable}]
        bu_context:     Business Unit name (for prompt context).
        domain_context: Data Domain names (for prompt context).

    Returns:
        A clean SQL string ready to execute against Databricks.
    """
    if not tables:
        raise ValueError("No tables in scope — assign tables to the selected BU/Domain first.")

    scope_desc = ""
    if bu_context:
        scope_desc += f"Business Unit: {bu_context}"
    if domain_context:
        scope_desc += f"  |  Data Domain(s): {', '.join(domain_context)}"

    table_blocks = []
    for t in tables:
        cat, sch, tbl = t["catalog"], t["schema"], t["table"]
        cols = sorted(t.get("columns", []), key=lambda x: int(x.get("ordinalPosition", 0)))
        cols = cols[:_MAX_COLS_PER_TABLE]
        col_lines = "\n".join(
            f"    {i+1}. `{c['colName']}`  {c['dataType']}"
            + (f"  -- {c['colComment'].strip()}" if c.get('colComment') else "")
            for i, c in enumerate(cols)
        )
        desc_line = f"\nDESCRIPTION: {t['description']}" if t.get("description") else ""
        block = (
            f"TABLE: `{cat}`.`{sch}`.`{tbl}`{desc_line}\n"
            f"COLUMNS ({len(cols)} shown):\n{col_lines}"
        )
        table_blocks.append(block)

    tables_section = "\n\n".join(table_blocks)

    system = f"""You are a SQL expert for Databricks Unity Catalog (Delta Lake / Spark SQL).

SCOPE: {scope_desc}

The following {len(tables)} table(s) are available in this scope:

{tables_section}

TASK:
- Read the user's question carefully.
- Identify which table(s) are relevant to answer it.
- Generate a single SQL query that answers the question.

RULES:
1. Use fully qualified, backtick-quoted table names: `catalog`.`schema`.`table`
2. Use backtick quoting for column names that contain spaces or special characters.
3. Default LIMIT 1000 unless the question implies a full aggregation or COUNT(*).
4. Never generate DROP, DELETE, TRUNCATE, UPDATE, INSERT, ALTER, CREATE, GRANT, REVOKE.
5. Use Databricks SQL / Spark SQL dialect (ANSI SQL with Spark extensions).
6. For string comparisons use ILIKE or LOWER() for case-insensitive matching.
7. If the question spans multiple tables, use JOIN with the appropriate keys.
8. Return ONLY the SQL query — no markdown fences, no commentary, no explanation.
"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": f"Generate SQL for: {question}"},
    ]

    logger.debug("nl_to_sql: question=%r tables=%d model=%s",
                 question, len(tables), settings.openai.sparql_model)

    try:
        resp = _chat_completion(settings.openai.sparql_model, messages, settings.openai.max_tokens)
    except Exception as exc:
        logger.warning("Primary model %s failed (%s), falling back to gpt-4o",
                       settings.openai.sparql_model, exc)
        resp = _chat_completion("gpt-4o", messages, settings.openai.max_tokens)

    raw = _content(resp.choices[0].message).strip()
    logger.debug("nl_to_sql raw: %r", raw[:300])
    return _sanitise_sql(raw)


def _sanitise_sql(raw: str) -> str:
    """Strip markdown fences and block dangerous statements."""
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw).strip()
    m = _FORBIDDEN.search(raw)
    if m:
        raise ValueError(f"Generated SQL contains forbidden keyword '{m.group()}'. Query blocked.")
    return raw
