"""Call the demand-forecast Model Serving endpoint — LIVE mode.

The app depends only on the request/response contract documented in
data_pipeline/forecasting_model.py, so pointing SERVING_ENDPOINT at Galenica's
real endpoint requires no code change (provided it honours the same contract).
"""
from .config import SERVING_ENDPOINT, get_workspace_client


def forecast(pharmacy_id: str, product_id: str, horizon: int = 28) -> list[dict]:
    """Query the serving endpoint for one series; return the forecast list."""
    w = get_workspace_client()
    resp = w.serving_endpoints.query(
        name=SERVING_ENDPOINT,
        dataframe_records=[
            {"pharmacy_id": pharmacy_id, "product_id": product_id, "horizon": horizon}
        ],
    )
    preds = resp.predictions
    # predictions is a list with one element per input row
    if isinstance(preds, list) and preds:
        first = preds[0]
        if isinstance(first, dict) and "forecast" in first:
            return first["forecast"]
    return []
