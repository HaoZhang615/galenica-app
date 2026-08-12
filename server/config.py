"""Runtime configuration + dual-mode auth for the Galenica demo backend.

Two execution contexts:
  * Databricks App  -> service-principal creds are auto-injected; resource
    bindings set PGHOST/PGUSER/... and DATABRICKS_WAREHOUSE_ID.
  * Local dev       -> uses a Databricks CLI profile (DATABRICKS_PROFILE).

Two data modes:
  * LIVE  -> queries the SQL warehouse, Lakebase, and the serving endpoints.
  * MOCK  -> serves in-process synthetic data (no Databricks needed). Enabled
    explicitly via DEMO_MOCK=1, or automatically when required live config
    (warehouse id / PG host) is absent. This keeps the UI fully demoable and
    lets the frontend be developed without a workspace.
"""
import functools
import os

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

CATALOG = os.environ.get("CATALOG", "galenica_demo")
SCHEMA = os.environ.get("SCHEMA", "forecasting")
SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "galenica-demand-forecast")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "databricks-claude-sonnet-4-5")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "").strip()

# AI Gateway URL for the LLM endpoint. When set, llm.py routes through the
# AI Gateway subdomain so usage appears in system.ai_gateway.usage and the
# "Total tokens (7d)" counter on the endpoint list page updates.
# Format: https://{workspace_id}.ai-gateway.cloud.databricks.com/mlflow/v1
# The configure_ai_gateway job task enables usage tracking on the endpoint;
# set this env var once the AI Gateway subdomain is provisioned for your workspace.
AI_GATEWAY_URL = os.environ.get("AI_GATEWAY_URL", "").strip()

WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "").strip()
PGHOST = os.environ.get("PGHOST", "").strip()


def _mock_forced() -> bool:
    return os.environ.get("DEMO_MOCK", "").lower() in ("1", "true", "yes")


@functools.lru_cache(maxsize=1)
def use_mock() -> bool:
    """Mock unless we have the live config we need (warehouse + Lakebase host)."""
    if _mock_forced():
        return True
    return not (WAREHOUSE_ID and PGHOST)


@functools.lru_cache(maxsize=1)
def get_workspace_client():
    """Authenticated WorkspaceClient (app SP remotely, CLI profile locally)."""
    from databricks.sdk import WorkspaceClient

    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "DEFAULT")
    return WorkspaceClient(profile=profile)


def get_oauth_token() -> str:
    """OAuth bearer token for the current identity."""
    client = get_workspace_client()
    headers = client.config.authenticate()
    if headers and "Authorization" in headers:
        return headers["Authorization"].replace("Bearer ", "")
    return client.config.token or ""


def get_workspace_host() -> str:
    """Workspace host URL, always with an https:// scheme."""
    if IS_DATABRICKS_APP:
        host = os.environ.get("DATABRICKS_HOST", "")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host
    return get_workspace_client().config.host
