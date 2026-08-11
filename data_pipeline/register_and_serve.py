"""Register the synthetic forecasting model in Unity Catalog and deploy it to a
real Model Serving endpoint.

Steps:
  1. Read dim_pharmacy + dim_product from Delta and build the per-series lookup.
  2. Log a pyfunc model (forecasting_model.GalenicaForecastModel) with that lookup
     baked in as an artifact.
  3. Register it in Unity Catalog as {catalog}.{schema}.demand_forecast_model.
  4. Create (or update) the Model Serving endpoint so the app can call it live.

Swap note: this is the "synthetic" model. Galenica keep their real endpoint and
just set the app's SERVING_ENDPOINT / bundle var `serving_endpoint_name` to it —
this script is only needed to stand up the demo model.
"""
import argparse
import json
import os
import tempfile

import mlflow
import pandas as pd
from pyspark.sql import SparkSession

from forecasting_model import GalenicaForecastModel


def build_series_lookup(spark, catalog, schema) -> dict:
    ph = spark.table(f"{catalog}.{schema}.dim_pharmacy").select("pharmacy_id", "size_factor")
    pr = spark.table(f"{catalog}.{schema}.dim_product").select(
        "product_id", "base_popularity", "seasonal_peak_month"
    )
    series = (
        ph.crossJoin(pr)
        .selectExpr(
            "pharmacy_id", "product_id",
            "round(size_factor * base_popularity, 4) as series_base",
            "seasonal_peak_month",
        )
        .collect()
    )
    return {
        f"{r['pharmacy_id']}|{r['product_id']}": [float(r["series_base"]), int(r["seasonal_peak_month"])]
        for r in series
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--endpoint-name", required=True)
    args = ap.parse_args()

    spark = SparkSession.builder.getOrCreate()

    print("[galenica] Building per-series lookup...")
    series = build_series_lookup(spark, args.catalog, args.schema)
    print(f"[galenica] {len(series):,} pharmacy x product series")

    tmpdir = tempfile.mkdtemp()
    series_path = os.path.join(tmpdir, "series.json")
    with open(series_path, "w") as f:
        json.dump(series, f)

    model_name = f"{args.catalog}.{args.schema}.demand_forecast_model"
    mlflow.set_registry_uri("databricks-uc")

    # Put the experiment under the running user's home so the run always has a home.
    try:
        from databricks.sdk import WorkspaceClient
        user = WorkspaceClient().current_user.me().user_name
        mlflow.set_experiment(f"/Users/{user}/galenica-forecast-demo")
    except Exception as e:  # fall back to default experiment
        print(f"[galenica] could not set experiment ({e}); using default")

    this_dir = os.path.dirname(os.path.abspath(__file__))
    input_example = pd.DataFrame(
        [{"pharmacy_id": "PH0001", "product_id": "SKU0001", "horizon": 28}]
    )

    print("[galenica] Logging + registering pyfunc model to Unity Catalog...")
    with mlflow.start_run(run_name="galenica-synthetic-forecast") as run:
        mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=GalenicaForecastModel(),
            artifacts={"series": series_path},
            code_paths=[os.path.join(this_dir, "forecasting_model.py")],
            input_example=input_example,
            registered_model_name=model_name,
            pip_requirements=["mlflow", "pandas"],
        )
    # Resolve the version we just registered.
    from mlflow.tracking import MlflowClient
    client = MlflowClient(registry_uri="databricks-uc")
    versions = client.search_model_versions(f"name='{model_name}'")
    version = max(int(v.version) for v in versions)
    print(f"[galenica] Registered {model_name} version {version}")

    deploy_endpoint(args.endpoint_name, model_name, str(version))
    print("[galenica] Model registered and serving endpoint ready.")


def deploy_endpoint(endpoint_name: str, model_name: str, version: str):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import (
        EndpointCoreConfigInput,
        ServedEntityInput,
    )

    w = WorkspaceClient()
    served = ServedEntityInput(
        entity_name=model_name,
        entity_version=version,
        scale_to_zero_enabled=True,
        workload_size="Small",
    )
    existing = {e.name for e in w.serving_endpoints.list()}
    if endpoint_name in existing:
        print(f"[galenica] Updating existing endpoint '{endpoint_name}' to v{version}...")
        w.serving_endpoints.update_config_and_wait(
            name=endpoint_name, served_entities=[served]
        )
    else:
        print(f"[galenica] Creating serving endpoint '{endpoint_name}'...")
        w.serving_endpoints.create_and_wait(
            name=endpoint_name,
            config=EndpointCoreConfigInput(served_entities=[served]),
        )


if __name__ == "__main__":
    main()
