"""Enable AI Gateway on the Foundation Model endpoint.

Runs as a job task in the setup/refresh job (see resources/forecasting_job.job.yml).
Calling put_ai_gateway is idempotent — safe to re-run on every refresh.

What this turns on:
  - usage_tracking_config: LLM call metrics appear in system.ai_gateway.usage,
    driving the "Total tokens (7d)" counter on the endpoint list page.

The forecast model endpoint is intentionally NOT wired through AI Gateway:
  - serving.py calls w.serving_endpoints.query() (SDK direct path, not the
    AI Gateway URL), so the gateway layer is bypassed anyway.
  - Guardrails / PII / chat-format features don't apply to structured pyfunc
    forecast requests.
"""
import argparse

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import AiGatewayUsageTrackingConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--llm-endpoint",
        default="databricks-claude-sonnet-4-5",
        help="Name of the Foundation Model serving endpoint to configure.",
    )
    args = ap.parse_args()

    w = WorkspaceClient()
    print(f"[galenica] Configuring AI Gateway on endpoint '{args.llm_endpoint}'...")
    w.serving_endpoints.put_ai_gateway(
        name=args.llm_endpoint,
        usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
    )
    print(f"[galenica] AI Gateway enabled (usage tracking). "
          f"LLM calls will appear in system.ai_gateway.usage (batched, ~10 min lag).")


if __name__ == "__main__":
    main()
