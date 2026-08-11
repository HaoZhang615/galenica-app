"""Lakebase (Postgres) connection pool — LIVE mode only.

Uses the official Databricks pattern: a custom psycopg Connection subclass that
mints a fresh OAuth token per physical connection, so tokens never go stale. The
pool recycles connections every 45 min (before the 1-hour token expiry).

The pool is created lazily (get_pool()) so importing this module never fails in
MOCK mode where PGHOST isn't set.
"""
import os

import psycopg
from psycopg_pool import ConnectionPool

from .config import get_workspace_client

_pool = None


class OAuthConnection(psycopg.Connection):
    """psycopg Connection that injects a fresh Lakebase OAuth token on connect."""

    @classmethod
    def connect(cls, conninfo="", **kwargs):
        w = get_workspace_client()
        endpoint = os.environ.get("PGAPPNAME") or os.environ.get("DATABRICKS_DATABASE_INSTANCE")
        # Prefer the app-injected instance credential; fall back to instance name.
        instance = os.environ.get("PGDATABASE_INSTANCE") or os.environ.get("LAKEBASE_INSTANCE")
        import uuid
        if instance:
            cred = w.database.generate_database_credential(
                request_id=str(uuid.uuid4()), instance_names=[instance]
            )
        else:
            # Databricks Apps inject an OAuth-capable identity; use ambient creds.
            headers = w.config.authenticate()
            token = headers["Authorization"].replace("Bearer ", "")
            cred = type("C", (), {"token": token})()
        kwargs["password"] = cred.token
        return super().connect(conninfo, **kwargs)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        host = os.environ["PGHOST"]
        port = os.environ.get("PGPORT", "5432")
        database = os.environ.get("PGDATABASE", "databricks_postgres")
        user = os.environ["PGUSER"]
        sslmode = os.environ.get("PGSSLMODE", "require")
        _pool = ConnectionPool(
            conninfo=f"dbname={database} user={user} host={host} port={port} sslmode={sslmode}",
            connection_class=OAuthConnection,
            min_size=1,
            max_size=10,
            max_lifetime=2700,  # 45 min — recycle before 1-hour token expiry
            open=False,
        )
    return _pool


def open_pool():
    get_pool().open(wait=True, timeout=30.0)


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
