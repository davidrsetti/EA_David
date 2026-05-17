"""core/sparql_feedback.py — SPARQL success/failure feedback loop for improving generation."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_PATH = Path(__file__).parent.parent / "logs" / "sparql_feedback.jsonl"


def _ensure_log() -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _append(record: dict) -> None:
    _ensure_log()
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.warning("sparql_feedback: could not write record: %s", exc)


def record_failure(
    question: str,
    sparql: str,
    error: str,
    corrected_sparql: str = "",
) -> None:
    _append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "failure",
        "question": question,
        "sparql": sparql,
        "error": error,
        "corrected_sparql": corrected_sparql,
        "row_count": 0,
    })


def record_success(question: str, sparql: str, row_count: int) -> None:
    _append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "success",
        "question": question,
        "sparql": sparql,
        "error": "",
        "corrected_sparql": "",
        "row_count": row_count,
    })


def get_correction_examples(limit: int = 5) -> list[dict]:
    _ensure_log()
    if not _LOG_PATH.exists():
        return []
    records = []
    try:
        with _LOG_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("corrected_sparql"):
                    records.append(rec)
    except Exception as exc:
        logger.warning("sparql_feedback: could not read log: %s", exc)
        return []
    return records[-limit:]


def build_feedback_prompt_section(limit: int = 5) -> str:
    examples = get_correction_examples(limit)
    if not examples:
        return ""
    lines = ["Recent corrections (learn from these):"]
    for ex in examples:
        q = ex.get("question", "")
        err = ex.get("error", "")
        corrected = ex.get("corrected_sparql", "")
        lines.append(f'Q: "{q}" → SPARQL failed with "{err}".')
        lines.append(f"Corrected: {corrected}")
    return "\n".join(lines)
