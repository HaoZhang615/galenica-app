"""SQL Warehouse query helper — LIVE mode only.

Runs analytics queries against the bound SQL Warehouse via the Databricks SDK's
Statement Execution API. Using the SDK (already a dependency) avoids pulling in
the heavy databricks-sql-connector + pyarrow/pandas stack, which keeps the app's
build small and reliable.

Accepts psycopg-style named params (%(name)s) for a consistent call site with
db.py; they're converted to the SDK's :name syntax. Result values are coerced to
native Python types using the result manifest's column types.
"""
import os
import re
import time

from databricks.sdk.service.sql import StatementParameterListItem, StatementState

from .config import get_workspace_client

_NAMED = re.compile(r"%\((\w+)\)s")


def _coerce(value, type_name: str):
    if value is None:
        return None
    t = (type_name or "").upper()
    try:
        if t in ("INT", "INTEGER", "LONG", "BIGINT", "SHORT", "SMALLINT", "BYTE", "TINYINT"):
            return int(value)
        if t in ("FLOAT", "DOUBLE", "DECIMAL", "REAL"):
            return float(value)
        if t in ("BOOLEAN", "BOOL"):
            return str(value).lower() == "true"
    except (ValueError, TypeError):
        return value
    return value


def query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a SQL query and return a list of dict rows with native-typed values."""
    params = params or {}
    statement = _NAMED.sub(r":\1", sql)
    sdk_params = (
        [StatementParameterListItem(name=k, value=(None if v is None else str(v)))
         for k, v in params.items()]
        or None
    )

    w = get_workspace_client()
    resp = w.statement_execution.execute_statement(
        warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"],
        statement=statement,
        parameters=sdk_params,
        wait_timeout="30s",
        on_wait_timeout="CONTINUE",
    )
    # Poll until the statement leaves a non-terminal state.
    while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(1.0)
        resp = w.statement_execution.get_statement(resp.statement_id)

    state = resp.status.state if resp.status else None
    if state != StatementState.SUCCEEDED:
        err = resp.status.error.message if (resp.status and resp.status.error) else "unknown error"
        raise RuntimeError(f"SQL statement failed ({state}): {err}")

    cols = resp.manifest.schema.columns if (resp.manifest and resp.manifest.schema) else []
    names = [c.name for c in cols]
    types = [c.type_name.value if hasattr(c.type_name, "value") else str(c.type_name) for c in cols]
    data = (resp.result.data_array if (resp.result and resp.result.data_array) else []) or []
    return [
        {names[i]: _coerce(row[i], types[i]) for i in range(len(names))}
        for row in data
    ]
