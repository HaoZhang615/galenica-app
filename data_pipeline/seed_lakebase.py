"""Create and seed the Lakebase (Postgres) operational store for the app.

Creates schema `app` with:
  - reorder_decisions : recommended vs decided reorder quantities (write-back target)
  - stockout_alerts   : open stockout/overstock alerts (acknowledged from the UI)
  - annotations       : free-text notes users attach to a pharmacy/product
  - user_prefs        : per-user favourites / theme
  - latest_forecast   : low-latency copy of the next-horizon forecast (fast reads)

Alerts + a few pending reorder recommendations are derived from the synthetic
Delta data so the demo opens with realistic, actionable content.

`latest_forecast` is materialised here as a plain copy for reliability. To make
it a true Lakebase *synced table* (auto-updated from Delta), see the note in the
README — it needs a primary key + CDC on the source and a sync pipeline.
"""
import argparse
import uuid

import psycopg
from databricks.sdk import WorkspaceClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

DDL = """
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.stockout_alerts (
    id              BIGSERIAL PRIMARY KEY,
    pharmacy_id     TEXT NOT NULL,
    product_id      TEXT NOT NULL,
    severity        TEXT NOT NULL,          -- 'critical' | 'warning' | 'overstock'
    forecast_demand_7d NUMERIC,
    on_hand         INTEGER,
    days_cover      NUMERIC,
    status          TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'acknowledged'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS app.reorder_decisions (
    id              BIGSERIAL PRIMARY KEY,
    pharmacy_id     TEXT NOT NULL,
    product_id      TEXT NOT NULL,
    recommended_qty INTEGER NOT NULL,
    decided_qty     INTEGER,
    status          TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    decided_by      TEXT,
    decided_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.annotations (
    id          BIGSERIAL PRIMARY KEY,
    pharmacy_id TEXT NOT NULL,
    product_id  TEXT,
    note        TEXT NOT NULL,
    author      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.user_prefs (
    user_email        TEXT PRIMARY KEY,
    favorite_pharmacies TEXT[],
    theme             TEXT DEFAULT 'system',
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.latest_forecast (
    pharmacy_id   TEXT NOT NULL,
    product_id    TEXT NOT NULL,
    forecast_date DATE NOT NULL,
    p10           NUMERIC,
    p50           NUMERIC,
    p90           NUMERIC,
    generated_at  TIMESTAMPTZ,
    PRIMARY KEY (pharmacy_id, product_id, forecast_date)
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON app.stockout_alerts (status, severity);
CREATE INDEX IF NOT EXISTS idx_reorder_status ON app.reorder_decisions (status);
CREATE INDEX IF NOT EXISTS idx_latest_fc_ph ON app.latest_forecast (pharmacy_id);

-- Grant the schema to PUBLIC so the Databricks App's service-principal Postgres
-- role (created only when the app is bound, i.e. AFTER this seed runs) can read
-- and write. This seed runs as the deploying user; without these grants the app
-- SP hits "permission denied for schema app". PUBLIC keeps the demo deploy simple;
-- for production, replace PUBLIC with the app SP's role and drop the rest.
GRANT USAGE ON SCHEMA app TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO PUBLIC;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT USAGE, SELECT ON SEQUENCES TO PUBLIC;
"""


def connect(instance_name: str) -> psycopg.Connection:
    """Open a psycopg connection to the Lakebase instance using an OAuth token."""
    w = WorkspaceClient()
    inst = w.database.get_database_instance(name=instance_name)
    host = inst.read_write_dns
    user = w.current_user.me().user_name  # Postgres role matches the Databricks identity
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()), instance_names=[instance_name]
    )
    print(f"[galenica] connecting to Lakebase {instance_name} at {host} as {user}")
    return psycopg.connect(
        host=host, dbname="databricks_postgres", user=user,
        password=cred.token, sslmode="require", autocommit=True,
    )


def compute_seed_frames(spark, catalog, schema):
    """Derive alerts + reorder recommendations + latest forecast from Delta."""
    spark.conf.set("spark.sql.shuffle.partitions", "16")
    # 7-day forecast demand per series
    demand = spark.sql(f"""
        SELECT pharmacy_id, product_id, SUM(forecast_p50) AS demand_7d
        FROM {catalog}.{schema}.fact_forecast
        WHERE forecast_date < date_add(current_date(), 7)
        GROUP BY pharmacy_id, product_id
    """)
    # synthetic on-hand inventory -> days of cover.
    # target days-of-cover ~ log-normal (median ~12d): healthy majority with a
    # critical/warning tail and occasional overstock. randn() gives N(0,1).
    risk = (
        demand
        .withColumn("target_cover", F.exp(F.log(F.lit(12.0)) + F.randn(11) * F.lit(0.8)))
        .withColumn("daily", F.col("demand_7d") / 7.0 + F.lit(0.001))
        .withColumn("on_hand", F.greatest(F.lit(0), F.round(F.col("target_cover") * F.col("daily")).cast("int")))
        .withColumn("days_cover", F.col("on_hand") / F.col("daily"))
    )
    # keep only actionable rows; sample to keep the seed light
    alerts = risk.selectExpr(
        "pharmacy_id", "product_id", "round(demand_7d,1) AS forecast_demand_7d",
        "on_hand", "round(days_cover,2) AS days_cover",
        """CASE WHEN days_cover < 2 THEN 'critical'
                WHEN days_cover < 4 THEN 'warning'
                WHEN days_cover > 60 THEN 'overstock' END AS severity""",
    ).where("severity IS NOT NULL").limit(600)

    alert_rows = [
        (r.pharmacy_id, r.product_id, r.severity, float(r.forecast_demand_7d),
         int(r.on_hand), float(r.days_cover))
        for r in alerts.collect()
    ]

    # reorder recommendations for the critical/warning alerts
    reorder_rows = [
        (pid, prod, max(1, int(round(dem * 2 - oh))))  # target ~2 weeks cover
        for (pid, prod, sev, dem, oh, dc) in alert_rows
        if sev in ("critical", "warning")
    ][:200]

    latest_rows = [
        (r.pharmacy_id, r.product_id, r.forecast_date, float(r.forecast_p10),
         float(r.forecast_p50), float(r.forecast_p90))
        for r in spark.table(f"{catalog}.{schema}.fact_forecast").collect()
    ]
    return alert_rows, reorder_rows, latest_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--instance", required=True)
    args = ap.parse_args()

    spark = SparkSession.builder.getOrCreate()

    print("[galenica] deriving seed data from Delta...")
    alert_rows, reorder_rows, latest_rows = compute_seed_frames(spark, args.catalog, args.schema)
    print(f"[galenica] {len(alert_rows)} alerts, {len(reorder_rows)} reorder recs, "
          f"{len(latest_rows)} latest-forecast rows")

    conn = connect(args.instance)
    with conn.cursor() as cur:
        cur.execute(DDL)
        # idempotent reseed
        cur.execute("TRUNCATE app.stockout_alerts, app.reorder_decisions, app.latest_forecast")

        cur.executemany(
            "INSERT INTO app.stockout_alerts "
            "(pharmacy_id, product_id, severity, forecast_demand_7d, on_hand, days_cover) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            alert_rows,
        )
        cur.executemany(
            "INSERT INTO app.reorder_decisions (pharmacy_id, product_id, recommended_qty) "
            "VALUES (%s,%s,%s)",
            reorder_rows,
        )
        # batch the (potentially large) latest_forecast copy
        cur.executemany(
            "INSERT INTO app.latest_forecast "
            "(pharmacy_id, product_id, forecast_date, p10, p50, p90) "
            "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            latest_rows,
        )
    conn.close()
    print("[galenica] Lakebase seed complete.")


if __name__ == "__main__":
    main()
