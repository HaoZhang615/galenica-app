"""SQL Warehouse query helper — LIVE mode only.

Runs analytics queries (historical sales, aggregates) against the bound SQL
Warehouse using the Databricks SQL connector with OAuth from the app identity.
"""
import functools
import os

from databricks import sql as dbsql

from .config import get_oauth_token, get_workspace_host


@functools.lru_cache(maxsize=1)
def _http_path() -> str:
    warehouse_id = os.environ["DATABRICKS_WAREHOUSE_ID"]
    return f"/sql/1.0/warehouses/{warehouse_id}"


def _server_hostname() -> str:
    return get_workspace_host().replace("https://", "").replace("http://", "")


def query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a SQL query and return a list of dict rows."""
    with dbsql.connect(
        server_hostname=_server_hostname(),
        http_path=_http_path(),
        access_token=get_oauth_token(),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
