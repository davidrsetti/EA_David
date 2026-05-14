"""
uc_to_stardog.py — Extract Unity Catalog technical metadata → StarDog.

Scope  : all accessible UC catalogs
Target : StarDog EKG_David database, named graph <urn:EKG_UC_David>
Run    : python uc_to_stardog.py
"""
from __future__ import annotations

import logging
import os
import sys
import warnings
from urllib.parse import quote

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)   # /Users/drs58706/david/EKG_David
sys.path.insert(0, _root)
sys.path.insert(0, _here)
os.chdir(_here)
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv(".env")

from databricks import sql as databricks_sql
from nexus.core.stardog_client import get_stardog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
DATABRICKS_HOST = "adb-4213617139033191.11.azuredatabricks.net"
HTTP_PATH       = "/sql/1.0/warehouses/aeb3dfb63c5b8d7f"
NAMED_GRAPH     = "urn:EKG_UC_David"
UC_NS           = "urn:databricks:uc:"
UC_ONT          = "urn:databricks:uc:ontology#"
BATCH_SIZE      = 2000         # triples per INSERT DATA
SKIP_CATALOGS   = {"__databricks_internal"}
SKIP_SCHEMAS    = {"information_schema"}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _enc(*parts: str) -> str:
    """URL-encode each path segment and join with /."""
    return "/".join(quote(str(p), safe="") for p in parts)


def _iri(*parts: str) -> str:
    return f"<{UC_NS}{_enc(*parts)}>"


def _lit(val) -> str:
    if val is None:
        return '""'
    s = (str(val)
         .replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
         .replace("\r", "\\r"))
    return f'"{s}"'


def _prefixes() -> str:
    return (
        f"PREFIX uc:   <{UC_ONT}>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>\n"
        "PREFIX dc:   <http://purl.org/dc/terms/>\n"
    )


def _insert_block(triples: list[str]) -> str:
    body = "\n    ".join(triples)
    return f"{_prefixes()}\nINSERT DATA {{\n  GRAPH <{NAMED_GRAPH}> {{\n    {body}\n  }}\n}}"


def _flush(stardog, triples: list[str]) -> None:
    if not triples:
        return
    for i in range(0, len(triples), BATCH_SIZE):
        batch = triples[i : i + BATCH_SIZE]
        stardog.update(_insert_block(batch))


# ── UC extraction ─────────────────────────────────────────────────────────────

def _fetch(cur, sql: str) -> list[dict]:
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        logger.warning("Query skipped (%s): %.120s", type(exc).__name__, sql)
        return []


def get_catalogs(cur) -> list[str]:
    cur.execute("SHOW CATALOGS")
    return [row[0] for row in cur.fetchall()]


def get_schemas(cur, catalog: str) -> list[dict]:
    return _fetch(cur, f"""
        SELECT catalog_name, schema_name, schema_owner, comment,
               created, created_by, last_altered, last_altered_by
        FROM `{catalog}`.information_schema.schemata
        WHERE schema_name NOT IN ('information_schema')
    """)


def get_tables(cur, catalog: str) -> list[dict]:
    return _fetch(cur, f"""
        SELECT table_catalog, table_schema, table_name, table_type,
               table_owner, comment, created, created_by,
               last_altered, last_altered_by,
               data_source_format, storage_path
        FROM `{catalog}`.information_schema.tables
        WHERE table_schema NOT IN ('information_schema')
    """)


def get_columns(cur, catalog: str) -> list[dict]:
    return _fetch(cur, f"""
        SELECT table_schema, table_name, column_name,
               ordinal_position, data_type, is_nullable, comment
        FROM `{catalog}`.information_schema.columns
        WHERE table_schema NOT IN ('information_schema')
        ORDER BY table_schema, table_name, ordinal_position
    """)


def get_table_tags(cur, catalog: str) -> list[dict]:
    return _fetch(cur, f"""
        SELECT schema_name, table_name, tag_name, tag_value
        FROM `{catalog}`.information_schema.table_tags
    """)


def get_column_tags(cur, catalog: str) -> list[dict]:
    return _fetch(cur, f"""
        SELECT schema_name, table_name, column_name, tag_name, tag_value
        FROM `{catalog}`.information_schema.column_tags
    """)


# ── Triple generation ─────────────────────────────────────────────────────────

def catalog_triples(catalog: str) -> list[str]:
    ci = _iri("catalog", catalog)
    return [
        f"{ci} a uc:Catalog .",
        f"{ci} rdfs:label {_lit(catalog)} .",
    ]


def schema_triples(catalog: str, s: dict) -> list[str]:
    schema = s["schema_name"]
    si = _iri("schema", catalog, schema)
    ci = _iri("catalog", catalog)
    t = [
        f"{si} a uc:Schema .",
        f"{si} rdfs:label {_lit(schema)} .",
        f"{si} uc:inCatalog {ci} .",
        f"{ci} uc:hasSchema {si} .",
    ]
    for field, pred in [
        ("schema_owner",    "uc:owner"),
        ("comment",         "rdfs:comment"),
        ("created_by",      "uc:createdBy"),
        ("last_altered_by", "uc:lastAlteredBy"),
    ]:
        if s.get(field):
            t.append(f"{si} {pred} {_lit(s[field])} .")
    for field, pred in [("created", "dc:created"), ("last_altered", "dc:modified")]:
        if s.get(field):
            t.append(f'{si} {pred} "{s[field]}"^^xsd:string .')
    return t


def table_triples(catalog: str, tbl: dict) -> list[str]:
    schema = tbl["table_schema"]
    table  = tbl["table_name"]
    ti = _iri("table",  catalog, schema, table)
    si = _iri("schema", catalog, schema)
    t = [
        f"{ti} a uc:Table .",
        f"{ti} rdfs:label {_lit(table)} .",
        f"{ti} uc:inSchema {si} .",
        f"{si} uc:hasTable {ti} .",
    ]
    for field, pred in [
        ("table_type",      "uc:tableType"),
        ("table_owner",     "uc:owner"),
        ("comment",         "rdfs:comment"),
        ("data_source_format", "uc:dataFormat"),
        ("storage_path",    "uc:storagePath"),
        ("created_by",      "uc:createdBy"),
        ("last_altered_by", "uc:lastAlteredBy"),
    ]:
        if tbl.get(field):
            t.append(f"{ti} {pred} {_lit(tbl[field])} .")
    for field, pred in [("created", "dc:created"), ("last_altered", "dc:modified")]:
        if tbl.get(field):
            t.append(f'{ti} {pred} "{tbl[field]}"^^xsd:string .')
    return t


def column_triples(catalog: str, col: dict) -> list[str]:
    schema  = col["table_schema"]
    table   = col["table_name"]
    colname = col["column_name"]
    ci_iri = _iri("column", catalog, schema, table, colname)
    ti     = _iri("table",  catalog, schema, table)
    t = [
        f"{ci_iri} a uc:Column .",
        f"{ci_iri} rdfs:label {_lit(colname)} .",
        f"{ci_iri} uc:inTable {ti} .",
        f"{ti} uc:hasColumn {ci_iri} .",
        f"{ci_iri} uc:dataType {_lit(col['data_type'])} .",
        f"{ci_iri} uc:ordinalPosition \"{col['ordinal_position']}\"^^xsd:integer .",
        f"{ci_iri} uc:isNullable \"{str(col.get('is_nullable','YES') == 'YES').lower()}\"^^xsd:boolean .",
    ]
    if col.get("comment"):
        t.append(f"{ci_iri} rdfs:comment {_lit(col['comment'])} .")
    return t


def tag_triples(subject_iri: str, tag_path: list[str], tag: dict) -> list[str]:
    tg = _iri("tag", *tag_path)
    t = [
        f"{tg} a uc:Tag .",
        f"{tg} uc:tagName {_lit(tag['tag_name'])} .",
        f"{subject_iri} uc:hasTag {tg} .",
    ]
    if tag.get("tag_value"):
        t.append(f"{tg} uc:tagValue {_lit(tag['tag_value'])} .")
    return t


# ── Ontology axioms (inserted once) ──────────────────────────────────────────

ONTOLOGY_TRIPLES = [
    # Classes
    "uc:Catalog a rdfs:Class ; rdfs:label \"UC Catalog\" .",
    "uc:Schema  a rdfs:Class ; rdfs:label \"UC Schema\" .",
    "uc:Table   a rdfs:Class ; rdfs:label \"UC Table\" .",
    "uc:Column  a rdfs:Class ; rdfs:label \"UC Column\" .",
    "uc:Tag     a rdfs:Class ; rdfs:label \"UC Tag\" .",
    # Properties
    "uc:hasSchema        rdfs:domain uc:Catalog ; rdfs:range uc:Schema .",
    "uc:hasTable         rdfs:domain uc:Schema  ; rdfs:range uc:Table .",
    "uc:hasColumn        rdfs:domain uc:Table   ; rdfs:range uc:Column .",
    "uc:hasTag           rdfs:comment \"Attaches a UC tag to any UC resource.\" .",
    "uc:inCatalog        rdfs:domain uc:Schema  ; rdfs:range uc:Catalog .",
    "uc:inSchema         rdfs:domain uc:Table   ; rdfs:range uc:Schema .",
    "uc:inTable          rdfs:domain uc:Column  ; rdfs:range uc:Table .",
    "uc:owner            a rdfs:Property ; rdfs:label \"owner\" .",
    "uc:tableType        a rdfs:Property ; rdfs:label \"table type\" .",
    "uc:dataFormat       a rdfs:Property ; rdfs:label \"data format\" .",
    "uc:dataType         a rdfs:Property ; rdfs:label \"column data type\" .",
    "uc:ordinalPosition  a rdfs:Property ; rdfs:label \"ordinal position\" .",
    "uc:isNullable       a rdfs:Property ; rdfs:label \"is nullable\" .",
    "uc:storagePath      a rdfs:Property ; rdfs:label \"storage path\" .",
    "uc:createdBy        a rdfs:Property ; rdfs:label \"created by\" .",
    "uc:lastAlteredBy    a rdfs:Property ; rdfs:label \"last altered by\" .",
    "uc:tagName          a rdfs:Property ; rdfs:label \"tag name\" .",
    "uc:tagValue         a rdfs:Property ; rdfs:label \"tag value\" .",
    # Governance classes (instances live in <urn:EKG_UC_Enrichment>)
    "uc:BusinessUnit     a rdfs:Class ; rdfs:label \"Business Unit\" .",
    "uc:DataDomain       a rdfs:Class ; rdfs:label \"Data Domain\" .",
    "uc:belongsToBU      rdfs:domain uc:Table ; rdfs:range uc:BusinessUnit ; rdfs:label \"belongs to BU\" .",
    "uc:belongsToDomain  rdfs:domain uc:Table ; rdfs:range uc:DataDomain   ; rdfs:label \"belongs to domain\" .",
]


# ── Main ──────────────────────────────────────────────────────────────────────

def _already_loaded(stardog, catalog: str) -> bool:
    """Return True if this catalog already has triples in the named graph."""
    cat_iri = f"<{UC_NS}catalog/{_enc(catalog)}>"
    result = stardog.query(
        f"ASK {{ GRAPH <{NAMED_GRAPH}> {{ {cat_iri} a <{UC_ONT}Catalog> }} }}"
    )
    return result.get("boolean", False)


def main(resume: bool = False) -> None:
    token = os.getenv("DATABRICKS_TOKEN")
    if not token:
        sys.exit("DATABRICKS_TOKEN not set")

    logger.info("Connecting to Databricks SQL warehouse…")
    conn = databricks_sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=HTTP_PATH,
        access_token=token,
        _tls_no_verify=True,
    )
    cur = conn.cursor()

    stardog = get_stardog()

    if resume:
        logger.info("RESUME mode — skipping already-loaded catalogs, keeping graph.")
    else:
        # ── Clear existing named graph ────────────────────────────────────────
        logger.info("Clearing named graph <%s>…", NAMED_GRAPH)
        stardog.update(f"DROP SILENT GRAPH <{NAMED_GRAPH}>")

        # ── Insert ontology axioms ────────────────────────────────────────────
        logger.info("Inserting ontology axioms…")
        _flush(stardog, ONTOLOGY_TRIPLES)

    # ── Enumerate catalogs ────────────────────────────────────────────────────
    catalogs = get_catalogs(cur)
    logger.info("Catalogs found: %s", catalogs)

    grand_total = 0

    for catalog in catalogs:
        if catalog in SKIP_CATALOGS:
            logger.info("Skipping %s", catalog)
            continue

        if resume and _already_loaded(stardog, catalog):
            logger.info("RESUME — already loaded, skipping: %s", catalog)
            continue

        logger.info("── Catalog: %s ──", catalog)

        schemas    = get_schemas(cur, catalog)
        tables     = get_tables(cur, catalog)
        columns    = get_columns(cur, catalog)
        tbl_tags   = get_table_tags(cur, catalog)
        col_tags   = get_column_tags(cur, catalog)

        logger.info("  schemas=%d  tables=%d  columns=%d", len(schemas), len(tables), len(columns))

        # Index tags and columns for fast lookup
        tbl_tag_idx: dict[tuple, list] = {}
        for tag in tbl_tags:
            tbl_tag_idx.setdefault((tag["schema_name"], tag["table_name"]), []).append(tag)

        col_tag_idx: dict[tuple, list] = {}
        for tag in col_tags:
            col_tag_idx.setdefault((tag["schema_name"], tag["table_name"], tag["column_name"]), []).append(tag)

        col_idx: dict[tuple, list] = {}
        for col in columns:
            col_idx.setdefault((col["table_schema"], col["table_name"]), []).append(col)

        triples: list[str] = []

        # Catalog node
        triples.extend(catalog_triples(catalog))

        # Schemas
        for s in schemas:
            triples.extend(schema_triples(catalog, s))

        # Tables + columns
        for tbl in tables:
            schema = tbl["table_schema"]
            table  = tbl["table_name"]

            triples.extend(table_triples(catalog, tbl))

            # Table tags
            for tag in tbl_tag_idx.get((schema, table), []):
                ti = _iri("table", catalog, schema, table)
                triples.extend(tag_triples(ti, [catalog, schema, table, tag["tag_name"]], tag))

            # Columns
            for col in col_idx.get((schema, table), []):
                colname = col["column_name"]
                triples.extend(column_triples(catalog, col))

                # Column tags
                for tag in col_tag_idx.get((schema, table, colname), []):
                    ci_iri = _iri("column", catalog, schema, table, colname)
                    triples.extend(tag_triples(ci_iri, [catalog, schema, table, colname, tag["tag_name"]], tag))

        _flush(stardog, triples)
        grand_total += len(triples)
        logger.info("  Loaded %d triples for catalog %s", len(triples), catalog)

    logger.info("All catalogs done. Total triples: %d", grand_total)

    # ── Verify ────────────────────────────────────────────────────────────────
    result = stardog.query(
        f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{NAMED_GRAPH}> {{ ?s ?p ?o }} }}"
    )
    _, rows = stardog.to_rows(result)
    logger.info("Verification — triples in <%s>: %s", NAMED_GRAPH, rows[0]["n"])

    cur.close()
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true",
                        help="Skip catalogs already present in the graph; continue from where a previous run left off.")
    args = parser.parse_args()
    main(resume=args.resume)
