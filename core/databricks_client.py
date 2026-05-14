"""
core/databricks_client.py — Singleton Databricks SQL connector.
Mirrors the StardogClient pattern: thin wrapper, safe for concurrent use.
"""
from __future__ import annotations

import logging
import warnings
from typing import Any

warnings.filterwarnings("ignore", category=Warning, module="urllib3")

from nexus.config.settings import settings

logger = logging.getLogger(__name__)

_client: "DatabricksClient | None" = None


class DatabricksError(Exception):
    """Raised for Databricks connection or query errors."""


class DatabricksClient:
    """
    Thin wrapper around databricks-sql-connector.
    Instantiate via get_databricks() — do not construct directly.
    """

    def __init__(self) -> None:
        from databricks import sql as _sql  # lazy import

        cfg = settings.databricks
        if not cfg.token:
            raise DatabricksError("DATABRICKS_TOKEN is not configured.")
        logger.debug("Opening Databricks SQL connection to %s", cfg.host)
        self._conn = _sql.connect(
            server_hostname=cfg.host,
            http_path=cfg.http_path,
            access_token=cfg.token,
            _tls_no_verify=True,
        )

    def query(self, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        """Execute a SELECT and return (columns, rows). rows[i] is a plain dict."""
        logger.debug("DATABRICKS SQL:\n%s", sql[:500])
        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            cur.close()
        return cols, rows

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


def get_databricks() -> DatabricksClient:
    global _client
    if _client is None:
        _client = DatabricksClient()
    return _client
