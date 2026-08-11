# Galenica — Demand Forecasting Demo (Databricks App)

An eye-catching, production-shaped demo of how **Databricks Apps** can serve
demand-forecasting model endpoints for **400+ pharmacies across Switzerland**,
combining **Model Serving**, **Lakebase (Postgres)**, a **SQL Warehouse**, and a
**Foundation Model** assistant — behind a modern **React + Vite + TypeScript +
Tailwind** frontend and a **FastAPI** backend.

Everything is **synthetic** (we don't use Galenica's real model or data) and the
whole stack is **infrastructure-as-code**: clone, set a handful of variables, and
deploy to your own Azure Databricks workspace.

> **Swap in your real model:** the app calls a Model Serving endpoint by name.
> Point the `serving_endpoint_name` variable at Galenica's production forecasting
> endpoint and the app uses it — no code change (see [Swapping in the real
> model](#swapping-in-the-real-model)).

---

## What's in the demo

| Screen | Shows |
| --- | --- |
| **Overview** | KPI row (7-day forecast demand, accuracy, critical stockouts, overstock), national actual-vs-forecast trend, highest-risk pharmacies |
| **Network map** | All pharmacies plotted on Switzerland, coloured by stockout risk, with a per-canton rollup; click to drill in |
| **Pharmacy detail** | Per-product forecast vs actual with p10–p90 confidence bands (served **live** from the model endpoint), reorder recommendation, and team **notes persisted to Lakebase** |
| **Alerts & reorders** | Paginated stockout/overstock alerts (acknowledge → Lakebase) and pending reorder decisions (approve/reject → Lakebase) |
| **Ask your data** | Natural-language assistant over the forecasting data via a Foundation Model, with generated-SQL transparency, sources, signed-in identity, and an AI-generated disclaimer |

### Architecture

```
React (Vite/TS/Tailwind)  ──►  FastAPI  ──►  SQL Warehouse   (historical + aggregate analytics, Delta)
                                        ├──►  Lakebase Postgres (alerts, reorders, notes, fast reads)
                                        ├──►  Model Serving     (on-demand forecasts — swappable)
                                        └──►  Foundation Model   (AI assistant, via AI Gateway)
```

Delta tables (`dim_pharmacy`, `dim_product`, `fact_sales_daily`, `fact_forecast`)
are the analytics source of truth; Lakebase holds operational/transactional state.

---

## Prerequisites

- **Azure Databricks workspace**, serverless-enabled (required for Lakebase +
  Foundation Models).
- **Databricks CLI** ≥ 0.240 — `databricks --version`.
- A **SQL Warehouse** (get its id: `databricks warehouses list -p <profile>`).
- Authenticated CLI profile: `databricks auth login --host <workspace-url> -p <profile>`.
- For local development: **Python 3.11+ / [uv](https://docs.astral.sh/uv/)** and **Node 18+**.

---

## Deploy in 5 steps

```bash
# 1. Clone
git clone <this-repo> galenica-app && cd galenica-app

# 2. Set your variables — edit databricks.yml, or pass --var on the CLI.
#    At minimum set warehouse_id (and host per target if not using the profile's).

# 3. Build the frontend (its output is deployed with the app)
cd frontend && npm install && npm run build && cd ..

# 4. Validate + deploy the bundle (creates the job, Lakebase instance, and app)
databricks bundle validate --strict -t dev -p <profile>
databricks bundle deploy            -t dev -p <profile>

# 5. Generate data + register/serve the model + seed Lakebase, then it's live
databricks bundle run forecasting_job -t dev -p <profile>
```

Open the app URL from `databricks apps list -p <profile>` (or the deploy output).
Application logs: append `/logz` to the app URL.

### Configuration variables (`databricks.yml`)

| Variable | Purpose |
| --- | --- |
| `catalog` / `schema` | Unity Catalog location for the synthetic tables |
| `warehouse_id` | SQL Warehouse the app queries for analytics **(required)** |
| `serving_endpoint_name` | Forecast endpoint the app calls — **set to your real one to swap** |
| `lakebase_instance` | Lakebase Postgres instance name |
| `llm_endpoint` | Foundation Model endpoint for the assistant |
| `app_name` | Databricks App name |

The app also reads matching env vars from `app.yaml` (`CATALOG`, `SCHEMA`,
`SERVING_ENDPOINT`, `LLM_ENDPOINT`, `AI_GATEWAY_URL`, `GENIE_SPACE_ID`). Keep
these in sync with the bundle variables.

---

## Local development

The backend runs in **MOCK mode** with zero Databricks dependencies (in-process
synthetic data), so you can develop the whole UI offline:

```bash
# Terminal 1 — backend (mock data)
DEMO_MOCK=1 uv run uvicorn app:app --reload --port 8000

# Terminal 2 — frontend (proxies /api to :8000)
cd frontend && npm run dev      # http://localhost:5173
```

Point it at real resources locally by setting `DATABRICKS_PROFILE`,
`DATABRICKS_WAREHOUSE_ID`, and the `PG*` env vars (then `DEMO_MOCK` off). The
backend automatically uses MOCK mode whenever the warehouse id / Lakebase host
are absent, and LIVE mode when they're present.

---

## Swapping in the real model

The app depends only on the request/response contract in
[`data_pipeline/forecasting_model.py`](data_pipeline/forecasting_model.py):

- **Request** (per series): `{pharmacy_id, product_id, horizon}`
- **Response** (per series): `{pharmacy_id, product_id, forecast: [{date, p10, p50, p90}, …]}`

To use Galenica's production endpoint, set `serving_endpoint_name` (bundle) /
`SERVING_ENDPOINT` (app.yaml) to its name. If the real endpoint's schema differs,
adapt the thin translation in [`server/serving.py`](server/serving.py) only.

---

## Making `latest_forecast` a true Lakebase synced table

The seed copies the forecast into `app.latest_forecast` for reliability. To make
it an auto-updating **synced table** from Delta instead, add a primary key + CDC
to `fact_forecast` and create a synced table (see the Databricks Lakebase docs);
the app's read path is unchanged.

---

## Repo layout

```
databricks.yml            DABs root (variables, targets, sync excludes)
resources/*.yml           Job, Lakebase instance, and App resources
data_pipeline/            Synthetic data generator, pyfunc model, register+serve, Lakebase seed
app.py, app.yaml          FastAPI entry + Databricks App runtime config
server/                   Backend: config, db (Lakebase), warehouse, serving, llm, repository, routes
frontend/                 React + Vite + TS + Tailwind + Recharts app
.github/workflows/        Optional CI/CD (validate + deploy)
```
