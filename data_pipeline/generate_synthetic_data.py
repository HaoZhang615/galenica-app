"""Generate synthetic demand-forecasting data for the Galenica demo.

Creates four Delta tables in Unity Catalog:
  - dim_pharmacy    : 400+ Swiss pharmacies with canton, city, geo coordinates
  - dim_product     : pharma SKUs (Rx/OTC) across categories, some seasonal
  - fact_sales_daily: daily units sold per pharmacy x product (history)
  - fact_forecast   : point forecast + p10/p50/p90 bands per pharmacy x product x horizon

Everything is generated with Spark so it scales and runs on serverless compute.
Demand embeds weekly + annual seasonality, seasonal-product peaks (flu/allergy),
promotions, a size factor per pharmacy, and noise — so charts look believable.

Run as a job task (see resources/forecasting_job.job.yml) or interactively:
    python generate_synthetic_data.py --catalog galenica_demo --schema forecasting
"""
import argparse
import datetime as dt

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

# --- Configuration knobs (defaults tuned for a snappy but rich demo) ----------
N_PHARMACIES = 420
HISTORY_DAYS = 545          # ~18 months of daily history
FORECAST_HORIZON = 28       # days of forward forecast
SEED = 42

# Swiss cantons: (code, name, representative lat, lon, population weight).
# Weights bias pharmacy placement toward populous cantons (ZH, BE, VD, AG, GE...).
CANTONS = [
    ("ZH", "Zürich", 47.37, 8.54, 155), ("BE", "Bern", 46.95, 7.45, 104),
    ("VD", "Vaud", 46.52, 6.63, 81), ("AG", "Aargau", 47.39, 8.05, 69),
    ("SG", "St. Gallen", 47.42, 9.37, 51), ("GE", "Genève", 46.20, 6.14, 50),
    ("LU", "Luzern", 47.05, 8.31, 42), ("TI", "Ticino", 46.19, 9.02, 35),
    ("VS", "Valais", 46.23, 7.36, 35), ("FR", "Fribourg", 46.80, 7.16, 32),
    ("BL", "Basel-Landschaft", 47.48, 7.73, 29), ("TG", "Thurgau", 47.57, 9.09, 28),
    ("SO", "Solothurn", 47.21, 7.54, 28), ("GR", "Graubünden", 46.66, 9.58, 20),
    ("BS", "Basel-Stadt", 47.56, 7.59, 20), ("NE", "Neuchâtel", 46.99, 6.93, 18),
    ("SZ", "Schwyz", 47.02, 8.65, 16), ("ZG", "Zug", 47.17, 8.52, 13),
    ("SH", "Schaffhausen", 47.70, 8.63, 8), ("JU", "Jura", 47.35, 7.16, 7),
    ("AR", "Appenzell A.Rh.", 47.39, 9.28, 6), ("NW", "Nidwalden", 46.96, 8.37, 4),
    ("GL", "Glarus", 47.04, 9.07, 4), ("OW", "Obwalden", 46.90, 8.24, 4),
    ("UR", "Uri", 46.77, 8.63, 4), ("AI", "Appenzell I.Rh.", 47.33, 9.41, 2),
]

# Galenica-style retail pharmacy banners, for flavour.
BANNERS = ["Amavita", "Sun Store", "Coop Vitality"]

# Product catalog: (category, is_rx, seasonal_peak_month or 0=non-seasonal, n_skus)
CATEGORIES = [
    ("Analgesics", False, 0, 8),
    ("Cold & Flu", False, 1, 8),          # winter peak
    ("Allergy", False, 4, 6),             # spring peak
    ("Vitamins & Supplements", False, 11, 8),  # late-autumn immunity push
    ("Dermatology", False, 7, 5),         # summer peak
    ("Digestive Health", False, 0, 5),
    ("Cardiovascular", True, 0, 6),
    ("Diabetes", True, 0, 5),
    ("Antibiotics", True, 2, 5),          # late-winter peak
    ("Respiratory", True, 12, 5),         # deep-winter peak
]

INGREDIENTS = {
    "Analgesics": ["Paracetamol", "Ibuprofen", "Aspirin", "Diclofenac", "Naproxen"],
    "Cold & Flu": ["Pseudoephedrine", "Xylometazoline", "Dextromethorphan", "Oscillococcinum"],
    "Allergy": ["Cetirizine", "Loratadine", "Fexofenadine", "Desloratadine"],
    "Vitamins & Supplements": ["Vitamin D3", "Magnesium", "Vitamin C", "Omega-3", "Zinc", "Iron"],
    "Dermatology": ["Hydrocortisone", "Bepanthen", "Sunscreen SPF50", "Salicylic Acid"],
    "Digestive Health": ["Omeprazole", "Loperamide", "Simethicone", "Lactulose"],
    "Cardiovascular": ["Atorvastatin", "Amlodipine", "Ramipril", "Bisoprolol", "Losartan"],
    "Diabetes": ["Metformin", "Gliclazide", "Sitagliptin", "Insulin Glargine"],
    "Antibiotics": ["Amoxicillin", "Azithromycin", "Ciprofloxacin", "Doxycycline"],
    "Respiratory": ["Salbutamol", "Budesonide", "Montelukast", "Fluticasone"],
}
FORMS = ["Tablets", "Capsules", "Syrup", "Drops", "Spray", "Cream", "Sachets"]
STRENGTHS = ["100mg", "200mg", "500mg", "1000mg", "5mg", "10mg", "20mg", "50mg"]


def get_spark() -> SparkSession:
    return SparkSession.builder.getOrCreate()


def build_pharmacies(spark):
    """420 pharmacies distributed across cantons by population weight."""
    import random
    rng = random.Random(SEED)
    total_w = sum(c[4] for c in CANTONS)
    rows = []
    for i in range(1, N_PHARMACIES + 1):
        r = rng.uniform(0, total_w)
        acc = 0.0
        canton = CANTONS[0]
        for c in CANTONS:
            acc += c[4]
            if r <= acc:
                canton = c
                break
        code, name, lat, lon, _ = canton
        # jitter coordinates within the canton
        plat = round(lat + rng.uniform(-0.18, 0.18), 5)
        plon = round(lon + rng.uniform(-0.25, 0.25), 5)
        banner = BANNERS[rng.randrange(len(BANNERS))]
        # size_factor scales baseline demand (small village vs city-center store)
        size_factor = round(rng.uniform(0.55, 1.9), 3)
        rows.append((
            f"PH{i:04d}", f"{banner} {name} {i:04d}", banner,
            code, name, f"{name}", plat, plon, size_factor,
        ))
    schema = T.StructType([
        T.StructField("pharmacy_id", T.StringType()),
        T.StructField("name", T.StringType()),
        T.StructField("banner", T.StringType()),
        T.StructField("canton_code", T.StringType()),
        T.StructField("canton_name", T.StringType()),
        T.StructField("city", T.StringType()),
        T.StructField("latitude", T.DoubleType()),
        T.StructField("longitude", T.DoubleType()),
        T.StructField("size_factor", T.DoubleType()),
    ])
    return spark.createDataFrame(rows, schema)


def build_products(spark):
    import random
    rng = random.Random(SEED + 1)
    rows = []
    pid = 0
    for category, is_rx, peak_month, n in CATEGORIES:
        ingredients = INGREDIENTS[category]
        for _ in range(n):
            pid += 1
            ing = ingredients[rng.randrange(len(ingredients))]
            form = FORMS[rng.randrange(len(FORMS))]
            strength = STRENGTHS[rng.randrange(len(STRENGTHS))]
            name = f"{ing} {strength} {form}"
            # baseline daily popularity across the network
            popularity = round(rng.uniform(3.0, 22.0) * (0.7 if is_rx else 1.2), 2)
            unit_price = round(rng.uniform(4.0, 45.0) * (1.6 if is_rx else 1.0), 2)
            rows.append((
                f"SKU{pid:04d}", name, category, ing, form, strength,
                bool(is_rx), int(peak_month), popularity, unit_price,
            ))
    schema = T.StructType([
        T.StructField("product_id", T.StringType()),
        T.StructField("name", T.StringType()),
        T.StructField("category", T.StringType()),
        T.StructField("ingredient", T.StringType()),
        T.StructField("form", T.StringType()),
        T.StructField("strength", T.StringType()),
        T.StructField("is_rx", T.BooleanType()),
        T.StructField("seasonal_peak_month", T.IntegerType()),
        T.StructField("base_popularity", T.DoubleType()),
        T.StructField("unit_price_chf", T.DoubleType()),
    ])
    return spark.createDataFrame(rows, schema)


def _demand_expr(base_col, date_col, peak_col):
    """Spark expression producing expected daily demand > 0.

    base * weekly_factor * annual_seasonal_factor * promo * noise.
    """
    dow = F.dayofweek(date_col)                       # 1=Sun ... 7=Sat
    doy = F.dayofyear(date_col)
    month = F.month(date_col)

    # Weekly pattern: quiet Sunday, busy Thu-Sat.
    weekly = (
        F.when(dow == 1, F.lit(0.45))
        .when(dow == 7, F.lit(1.15))
        .when(dow.isin(5, 6), F.lit(1.20))
        .otherwise(F.lit(1.0))
    )

    # Annual seasonality for seasonal products: cosine peak at seasonal_peak_month.
    # peak==0 => flat (non-seasonal).
    peak_doy = (peak_col - F.lit(1)) * F.lit(30.4) + F.lit(15)
    seasonal_strength = F.when(peak_col == 0, F.lit(0.0)).otherwise(F.lit(0.6))
    annual = F.lit(1.0) + seasonal_strength * F.cos(
        (F.lit(2 * 3.141592653589793) / F.lit(365.0)) * (doy - peak_doy)
    )

    # Mild general winter uplift (people buy more health products in winter).
    winter = F.lit(1.0) + F.lit(0.10) * F.cos(
        (F.lit(2 * 3.141592653589793) / F.lit(365.0)) * (doy - F.lit(15))
    )

    # Random promo spikes (~4% of days) and multiplicative noise.
    promo = F.when(F.rand(SEED + 7) < F.lit(0.04), F.lit(1.8)).otherwise(F.lit(1.0))
    noise = F.lit(0.75) + F.rand(SEED + 9) * F.lit(0.5)   # 0.75 .. 1.25

    demand = base_col * weekly * annual * winter * promo * noise
    return F.greatest(F.lit(0.0), demand)


def build_sales_and_forecast(spark, pharmacies, products, catalog, schema):
    today = dt.date.today()
    hist_start = today - dt.timedelta(days=HISTORY_DAYS)

    # Cross join pharmacies x products -> per-series baseline.
    series = (
        pharmacies.select("pharmacy_id", "size_factor")
        .crossJoin(products.select("product_id", "base_popularity", "seasonal_peak_month"))
        .withColumn("series_base", F.col("size_factor") * F.col("base_popularity"))
    )

    # ---- Historical daily sales ------------------------------------------------
    date_hist = spark.sql(
        f"SELECT explode(sequence(to_date('{hist_start}'), to_date('{today - dt.timedelta(days=1)}'), interval 1 day)) AS sale_date"
    )
    sales = (
        series.crossJoin(date_hist)
        .withColumn("expected", _demand_expr(F.col("series_base"), F.col("sale_date"), F.col("seasonal_peak_month")))
        # units sold ~ round(expected) with a floor of 0
        .withColumn("units_sold", F.round(F.col("expected")).cast("int"))
        .select("pharmacy_id", "product_id", "sale_date", "units_sold")
    )
    (
        sales.write.mode("overwrite").format("delta")
        .option("overwriteSchema", "true")
        .partitionBy("sale_date")
        .saveAsTable(f"{catalog}.{schema}.fact_sales_daily")
    )

    # ---- Forward forecast with p10/p50/p90 bands -------------------------------
    date_fc = spark.sql(
        f"SELECT explode(sequence(to_date('{today}'), to_date('{today + dt.timedelta(days=FORECAST_HORIZON - 1)}'), interval 1 day)) AS forecast_date"
    )
    # Uncertainty widens with horizon (day index).
    forecast = (
        series.crossJoin(date_fc)
        .withColumn("day_idx", F.datediff(F.col("forecast_date"), F.lit(str(today))))
        .withColumn("p50", _demand_expr(F.col("series_base"), F.col("forecast_date"), F.col("seasonal_peak_month")))
        .withColumn("rel_sigma", F.lit(0.12) + F.lit(0.010) * F.col("day_idx"))
        .withColumn("p10", F.greatest(F.lit(0.0), F.col("p50") * (F.lit(1.0) - F.lit(1.2816) * F.col("rel_sigma"))))
        .withColumn("p90", F.col("p50") * (F.lit(1.0) + F.lit(1.2816) * F.col("rel_sigma")))
        .withColumn("generated_at", F.current_timestamp())
        .select(
            "pharmacy_id", "product_id", "forecast_date",
            F.round("p10", 1).alias("forecast_p10"),
            F.round("p50", 1).alias("forecast_p50"),
            F.round("p90", 1).alias("forecast_p90"),
            "generated_at",
        )
    )
    (
        forecast.write.mode("overwrite").format("delta")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{catalog}.{schema}.fact_forecast")
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    args = ap.parse_args()

    spark = get_spark()
    # CREATE CATALOG fails on workspaces where the metastore has no storage root
    # configured (common on FEVM classic workspaces). Create the catalog via the
    # Databricks UI first (Data > Create catalog), then re-run this job.
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {args.catalog}")
    except Exception as e:
        if "INVALID_STATE" in str(e) or "storage root" in str(e).lower():
            print(f"[galenica] WARNING: Could not auto-create catalog '{args.catalog}' "
                  f"(metastore has no storage root). Assuming it already exists.")
        else:
            raise
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{args.schema}")

    print(f"[galenica] Building dim_pharmacy ({N_PHARMACIES} pharmacies)...")
    pharmacies = build_pharmacies(spark)
    pharmacies.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(
        f"{args.catalog}.{args.schema}.dim_pharmacy"
    )

    print("[galenica] Building dim_product...")
    products = build_products(spark)
    products.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(
        f"{args.catalog}.{args.schema}.dim_product"
    )

    print("[galenica] Building fact_sales_daily + fact_forecast (this is the heavy step)...")
    build_sales_and_forecast(spark, pharmacies, products, args.catalog, args.schema)

    for t in ["dim_pharmacy", "dim_product", "fact_sales_daily", "fact_forecast"]:
        n = spark.table(f"{args.catalog}.{args.schema}.{t}").count()
        print(f"[galenica] {args.catalog}.{args.schema}.{t}: {n:,} rows")

    print("[galenica] Synthetic data generation complete.")


if __name__ == "__main__":
    main()
