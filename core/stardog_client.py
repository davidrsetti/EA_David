"""
core/stardog_client.py — Raw HTTP SPARQL client for Stardog.
Handles auth, query execution, EXPLAIN, and triple insertion.
"""
from __future__ import annotations
import logging
import ssl
from typing import Any
import requests
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.util.retry import Retry

import nexus.config.settings as _settings_module
from nexus.config.ontology_prefixes import SPARQL_PREFIX_BLOCK

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


def _build_session() -> requests.Session:
    """Session with retries for transient SSL EOF / connection drops (Zscaler-friendly)."""
    s = requests.Session()
    retry = Retry(
        total=3, connect=3, read=3,
        backoff_factor=0.6,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    s.mount("https://", adapter)
    s.mount("http://",  adapter)
    return s


class StardogError(Exception):
    """Raised for Stardog HTTP or SPARQL errors."""


class StardogClient:
    """
    Thin HTTP wrapper around Stardog's SPARQL endpoint.
    Instantiate once and reuse — safe for concurrent use.
    """

    def __init__(self):
        cfg = _settings_module.settings.stardog
        if not cfg.endpoint:
            raise StardogError("STARDOG_ENDPOINT is not configured.")
        self._endpoint  = cfg.endpoint
        self._token     = cfg.token
        self._scheme    = cfg.auth_scheme
        self._verify    = cfg.verify_tls
        self._timeout   = cfg.timeout
        self._session   = _build_session()

    # ── Auth headers ───────────────────────────────────────────────

    def _headers(self, accept: str = "application/sparql-results+json") -> dict:
        h = {"Accept": accept}
        if self._token:
            h["Authorization"] = f"{self._scheme} {self._token}"
        return h

    # ── Transport with SSL-EOF retry ───────────────────────────────

    def _post(self, url: str, *, data: bytes, headers: dict) -> requests.Response:
        """POST with up to 3 attempts on SSL EOF / ConnectionError (Zscaler drops idle TLS)."""
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return self._session.post(
                    url, data=data, headers=headers,
                    verify=self._verify, timeout=self._timeout,
                )
            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    ssl.SSLEOFError) as exc:
                last_exc = exc
                logger.warning("Stardog POST attempt %d failed: %s", attempt + 1, exc)
                # Drop pooled connections — the server already closed them.
                self._session.close()
                self._session = _build_session()
        raise StardogError(f"Stardog unreachable after 3 attempts: {last_exc}")

    # ── SELECT / ASK / CONSTRUCT ───────────────────────────────────

    def query(self, sparql: str, inject_prefixes: bool = False) -> dict[str, Any]:
        """Execute a SELECT/ASK/CONSTRUCT and return the parsed JSON."""
        full_query = (SPARQL_PREFIX_BLOCK + "\n\n" + sparql) if inject_prefixes else sparql
        logger.debug("SPARQL QUERY:\n%s", full_query)

        resp = self._post(
            self._endpoint,
            data=full_query.encode("utf-8"),
            headers={**self._headers(), "Content-Type": "application/sparql-query"},
        )
        self._raise_for_status(resp)
        return resp.json()

    # ── UPDATE (INSERT/DELETE) ─────────────────────────────────────

    def update(self, sparql_update: str) -> bool:
        """Execute a SPARQL UPDATE (INSERT DATA / DELETE DATA). Returns True on success."""
        logger.debug("SPARQL UPDATE:\n%s", sparql_update)
        update_endpoint = self._endpoint.replace("/query", "/update")

        resp = self._post(
            update_endpoint,
            data=sparql_update.encode("utf-8"),
            headers={**self._headers("application/json"), "Content-Type": "application/sparql-update"},
        )
        self._raise_for_status(resp)
        return True

    # ── EXPLAIN (query plan / complexity check) ────────────────────

    def explain(self, sparql: str) -> str:
        """Return Stardog's EXPLAIN plan for a query (text/plain)."""
        explain_endpoint = self._endpoint.replace("/query", "/explain")
        resp = self._post(
            explain_endpoint,
            data=sparql.encode("utf-8"),
            headers={**self._headers("text/plain"), "Content-Type": "application/sparql-query"},
        )
        self._raise_for_status(resp)
        return resp.text

    # ── Complexity heuristic ───────────────────────────────────────

    def estimate_complexity(self, sparql: str) -> int:
        """
        Structural complexity score based on query shape, not variable count.

        Scoring:
          +1  per triple pattern  (subject-predicate-object inside WHERE)
          +2  per OPTIONAL block
          +3  per UNION branch
          +4  per SERVICE call     (federated query — expensive)
          +3  per SUBQUERY / nested SELECT
          +1  per FILTER

        A well-formed 3-hop capability + app query scores ~8.
        A complex cross-domain query with 3 OPTIONALs scores ~12.
        Federated or deeply nested queries score 15+.
        Default limit of 25 blocks only truly pathological queries.
        """
        upper = sparql.upper()

        # Extract just the WHERE clause body for triple counting
        where_start = upper.find("WHERE")
        where_body = upper[where_start:] if where_start != -1 else upper

        # Count triple patterns: lines with a predicate (contain at least two ?
        # or a prefix:name pattern) — approximated by counting " ." and " ;"
        triple_score = where_body.count(" .") + where_body.count(" ;")

        score = (
            max(triple_score // 2, 1)          # triple patterns (dampened)
            + upper.count("OPTIONAL")  * 2
            + upper.count("UNION")     * 3
            + upper.count("SERVICE")   * 4
            + upper.count("SUBQUERY")  * 3
            + upper.count("FILTER")    * 1
        )
        return score

    # ── Normalise results ──────────────────────────────────────────

    @staticmethod
    def to_rows(result: dict) -> tuple[list[str], list[dict[str, str]]]:
        """
        Convert standard SELECT JSON to (columns, rows).
        rows[i] is a plain dict of {col: value_string}.
        """
        if "boolean" in result:
            return ["result"], [{"result": str(result["boolean"])}]

        columns = result.get("head", {}).get("vars", [])
        rows = [
            {col: b.get(col, {}).get("value", "") for col in columns}
            for b in result.get("results", {}).get("bindings", [])
        ]
        return columns, rows

    # ── Error handling ─────────────────────────────────────────────

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if not resp.ok:
            raise StardogError(
                f"Stardog HTTP {resp.status_code}: {resp.text[:500]}"
            )


# Singleton
_client: StardogClient | None = None


def get_stardog() -> StardogClient:
    global _client
    if _client is None:
        _client = StardogClient()
    return _client
