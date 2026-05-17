from __future__ import annotations
import csv, logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.config.ontology_prefixes import SPARQL_PREFIX_BLOCK

logger = logging.getLogger(__name__)

SUPPORTED_TYPES: dict[str, str] = {
    "Application":        "app:Application",
    "BusinessCapability": "ea:BusinessCapabilityL3",
    "DataProduct":        "data:DataProduct",
    "AIAgent":            "ai:Agent",
    "Integration":        "intg:Integration",
    "Person":             "hr:Person",
}

_IRI_BASE: dict[str, str] = {
    "Application":        "https://ontology.ea.example.org/app#",
    "BusinessCapability": "https://ontology.ea.example.org/ea#cap_",
    "DataProduct":        "https://ontology.ea.example.org/data#",
    "AIAgent":            "https://ontology.ea.example.org/ai#",
    "Integration":        "https://ontology.ea.example.org/intg#",
    "Person":             "https://ontology.ea.example.org/hr#",
}


@dataclass
class PopulationResult:
    source: str
    entity_type: str
    total_records: int
    triples_inserted: int
    errors: list[str] = field(default_factory=list)
    success: bool = True


def _make_iri(entity_type: str, label: str) -> str:
    slug = label.replace(" ", "_").replace("/", "_")[:60]
    base = _IRI_BASE.get(entity_type, "https://ontology.ea.example.org/nexus#")
    return f"{base}{slug}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _records_to_triples(
    records: list[dict],
    entity_type: str,
    field_map: dict[str, str],
) -> list[str]:
    rdf_type = SUPPORTED_TYPES.get(entity_type, f"nexus:{entity_type}")

    # Determine which source key maps to rdfs:label
    label_key: str | None = None
    for src_key, predicate in field_map.items():
        if predicate == "rdfs:label":
            label_key = src_key
            break
    # Fall back to first key in map if none explicitly mapped
    if label_key is None and field_map:
        label_key = next(iter(field_map))

    triples: list[str] = []
    for record in records:
        raw_label = str(record.get(label_key, "unknown")) if label_key else "unknown"
        iri = _make_iri(entity_type, raw_label)
        safe_label = _escape(raw_label)

        triples.append(f'<{iri}> a {rdf_type} .')
        triples.append(f'<{iri}> rdfs:label "{safe_label}"@en .')

        for src_key, predicate in field_map.items():
            if predicate == "rdfs:label":
                continue
            value = str(record.get(src_key, "")).strip()
            if not value:
                continue
            safe_val = _escape(value)
            triples.append(f'<{iri}> {predicate} "{safe_val}"^^xsd:string .')

    return triples


def _batch_insert(db, triples: list[str], batch_size: int = 500) -> int:
    inserted = 0
    for i in range(0, len(triples), batch_size):
        chunk = triples[i : i + batch_size]
        triple_block = "\n  ".join(chunk)
        sparql = f"{SPARQL_PREFIX_BLOCK}\nINSERT DATA {{\n  {triple_block}\n}}"
        db.update(sparql)
        inserted += len(chunk)
    return inserted


def populate_from_records(
    records: list[dict[str, Any]],
    entity_type: str,
    field_map: dict[str, str],
    source_label: str = "manual",
) -> PopulationResult:
    if entity_type not in SUPPORTED_TYPES:
        return PopulationResult(
            source=source_label,
            entity_type=entity_type,
            total_records=len(records),
            triples_inserted=0,
            errors=[f"Unsupported entity type: {entity_type}"],
            success=False,
        )

    from nexus.core.stardog_client import get_stardog
    db = get_stardog()

    triples = _records_to_triples(records, entity_type, field_map)
    errors: list[str] = []
    inserted = 0

    try:
        inserted = _batch_insert(db, triples)
    except Exception as exc:
        logger.error("populate_from_records failed: %s", exc)
        errors.append(str(exc))

    return PopulationResult(
        source=source_label,
        entity_type=entity_type,
        total_records=len(records),
        triples_inserted=inserted,
        errors=errors,
        success=len(errors) == 0,
    )


def populate_from_csv(
    filepath: str | Path,
    entity_type: str,
    field_map: dict[str, str],
) -> PopulationResult:
    path = Path(filepath)
    try:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            records = list(reader)
    except Exception as exc:
        return PopulationResult(
            source=str(filepath),
            entity_type=entity_type,
            total_records=0,
            triples_inserted=0,
            errors=[f"CSV read error: {exc}"],
            success=False,
        )

    return populate_from_records(records, entity_type, field_map, source_label=path.name)


def populate_from_databricks(
    sql: str,
    entity_type: str,
    field_map: dict[str, str],
) -> PopulationResult:
    try:
        from nexus.core.databricks_client import get_databricks
        db = get_databricks()
        cols, rows = db.query(sql)
    except Exception as exc:
        return PopulationResult(
            source="databricks",
            entity_type=entity_type,
            total_records=0,
            triples_inserted=0,
            errors=[f"Databricks query error: {exc}"],
            success=False,
        )

    return populate_from_records(rows, entity_type, field_map, source_label="databricks")
