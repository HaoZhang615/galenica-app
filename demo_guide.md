# Galenica Demand Forecasting — Demo Guide

A step-by-step script for demoing the app to Galenica. Built for a Databricks
Field Engineer / SA presenting live to a mixed business + data/ML audience.

- **Live app:** https://galenica-forecast-demo-7405617562494057.17.azure.databricksapps.com
- **Duration:** ~15 min core walkthrough (5-min and 30-min variants at the end)
- **Data:** fully synthetic — 420 pharmacies across all 26 cantons, 61 SKUs,
  banners you'll recognize (Amavita, Sun Store, Coop Vitality). No real Galenica
  data is used.

---

## 1. The one-sentence story

> "You already run demand-forecasting models on Azure Databricks Model Serving.
> This shows how a **Databricks App** turns those model endpoints into a tool your
> category and supply-chain teams actually use every day — and the whole thing is
> **infrastructure-as-code you clone and deploy in your own workspace**, pointing
> at *your* model with a single config change."

The three things you want them to remember:
1. **One platform, end to end** — the model, the analytics tables, the operational
   database, the AI assistant, and the app all live in *their* Databricks workspace.
   No new vendor, no data leaving governance.
2. **Live model serving, not a mockup** — the forecasts come from a real Model
   Serving endpoint. Swapping in Galenica's production model is a one-line change.
3. **Cloneable** — it's a Databricks Asset Bundle. They `git clone`, set a few
   variables, deploy. Nothing bespoke to maintain.

---

## 2. Audience framing (pick the language before you start)

| If the room is mostly… | Lead with… | Downplay… |
| --- | --- | --- |
| Business / supply chain | the daily workflow: alerts → decide reorder → act | the architecture diagram |
| Data / ML / platform | serving endpoint swap, Lakebase, DABs, governance | the UI polish |
| Mixed (most likely) | the workflow first, then "and here's how it's built" | — |

---

## 3. Pre-demo checklist (do this ~10 min before)

- [ ] **Open the app and warm it up.** First request after idle can be slow while
      the app container wakes. Load every page once so they're cached.
- [ ] **Confirm it says "Live data."** Top-left badge should read **Live data**
      (not "Demo data") with `galenica_demo.forecasting` next to it. That badge is
      your proof the numbers are coming from the warehouse + a live endpoint, not a
      canned mock.
- [ ] **Check the footer:** it should show **Databricks App · Lakebase** and
      **Model: galenica-demand-forecast** — visual proof of the moving parts.
- [ ] **Sign-in identity** (top-right) shows the logged-in user — mention this is
      real SSO identity, used for governance and write-back attribution.
- [ ] **Browser:** full-screen, 100–110% zoom, close other tabs. Have the repo open
      in a second window/IDE for the "how it's built" moment.
- [ ] **Backup:** if Wi-Fi is shaky, have screenshots of each page ready. The app
      also runs locally in **mock mode** (`npm run dev`) with zero Databricks
      dependencies — a reliable offline fallback that looks identical.
- [ ] **Pick one pharmacy to drill into** ahead of time (e.g. a high-risk one from
      the Overview list) so you don't hunt live.

---

## 4. Core walkthrough (~15 min)

Navigation lives in the left rail: **Overview · Network map · Alerts & reorders ·
Ask your data**. Follow that order — it's a deliberate narrative from "the big
picture" to "the daily decision" to "ask anything."

### Step 0 — Open on Overview, set the frame (30 sec)

> "This is a demand-forecasting cockpit for Galenica's ~400-pharmacy network.
> Everything you see is running in a Databricks workspace — I'll show you the
> plumbing at the end, but let's start where a category manager would."

Point at the **Live data** badge and the freshness timestamp under the title:
> "These aren't screenshots — the KPIs are live queries and the forecasts come
> from a model endpoint."

### Step 1 — Overview: the network at a glance (2–3 min)

The title itself carries the message ("N pharmacies need attention" or "Network
demand is on track") — read it out; that's message-in-title design.

Walk the **four KPI cards** left to right, each with its unit and period:
- **Forecast demand · 7d** — total predicted units next week.
- **Forecast accuracy** — headline model quality proxy.
- **Critical stockouts** — with warnings and pharmacies-at-risk underneath.
- **Overstock signals** — the other tail: capital tied up in excess inventory.

> "One line each way: understock loses sales and frustrates patients; overstock
> ties up cash and risks expiry. The app watches both."

Then the **National demand — actual vs forecast** chart:
> "History in one color, forecast in another — honest scenario marks, no blending.
> This is the served model's output aggregated to national level."

Finish on **Highest-risk pharmacies** (ranked by weighted alert severity):
> "This is the worklist. Let's see where they are." → click through to the map, or
> click a pharmacy to drill in.

### Step 2 — Network map: geography of risk (2–3 min)

Real Switzerland — country outline, all 26 canton borders, lakes. Every pharmacy
is a dot **colored by its highest active alert** (red = critical, orange = warning,
blue = overstock, green = healthy); **dot size ∝ pharmacy volume**.

Do these live:
- **Scroll to zoom / drag to pan** into a dense region (e.g. Zürich/Mittelland).
  > "400+ sites cluster in the population centers — zoom in and each becomes an
  > individually selectable site."
- **Hover a dot** → tooltip with name, canton, and alert counts.
- Glance at the **By canton** panel on the right (critical alerts, descending).
  > "Supply-chain leadership thinks in cantons and regions; the network view and
  > the canton rollup answer 'where do I send attention first?'"
- **Click a red dot** → drill into that pharmacy.

### Step 3 — Pharmacy detail: the forecast, up close (3–4 min)

This is the "real model serving" money shot.

- Pick a **product** from the list on the left (click one).
- The chart shows **90 days actual → 28 days forecast with an 80% interval
  (p10–p90 band)**.
  > "The line is the model's central forecast; the shaded band is its uncertainty.
  > This exact call hits a **Model Serving endpoint** — the same kind of endpoint
  > you already operate. If your model returns quantiles, they render here."
- Point to the **Recommended reorder** figure.
  > "The forecast becomes an action: a recommended reorder quantity to hit target
  > cover."
- **Notes (write-back):** type a note and hit enter.
  > "That just wrote to **Lakebase** — Postgres inside Databricks — attributed to
  > my signed-in identity. Forecasts and history live in Delta for analytics;
  > operational state like notes, decisions, and acknowledgements lives in Lakebase
  > for low-latency reads and writes. One platform, right tool for each job."

### Step 4 — Alerts & reorders: the daily decision loop (2–3 min)

Two tabs: **Alerts** and **Reorders**. Both write back to Lakebase.

- **Alerts tab:** filter by severity and by **Open / Acknowledged / All**. Show
  server-side pagination briefly.
  > "This is the morning worklist." → **Acknowledge** an alert. It stamps *your*
  > name and moves it out of the open queue in real time.
- **Reorders tab:** show a pending recommendation → **approve / adjust the
  quantity**.
  > "Recommended vs decided quantity, with who decided and when. That's an auditable
  > operational record — exactly what Lakebase is for, and it's governed alongside
  > everything else."

> "So the loop is complete: model predicts → app surfaces the risk → a human
> decides → the decision is recorded. All inside Databricks."

### Step 5 — Ask your data: the AI assistant (2 min)

Click a suggested prompt or type one:
- "Which pharmacies are at highest stockout risk?"
- "How is demand distributed by canton?"
- "What's the total forecast demand this week?"

When the answer returns, **point at three things**:
1. The **Generated SQL** panel — "you can see exactly how the answer was computed."
2. The **Sources** (the tables it used) — "grounded in your governed tables."
3. The persistent **"AI-generated — verify"** disclaimer, and that it ran as the
   signed-in identity.

> "This is a Databricks **Foundation Model** endpoint. Business users ask in plain
> language; the answer is transparent and auditable — not a black box."

### Step 6 — The differentiator: swap in *your* model (1–2 min)

This is the close. Flip to the repo in your IDE and show `databricks.yml`:

```yaml
serving_endpoint_name:
  default: galenica-demand-forecast   # ← change to your real endpoint name
```

> "Everything you just saw runs against a synthetic model *we* deployed. To point
> this at Galenica's production forecasting endpoint, you change **this one value**
> and redeploy. No code changes. The app doesn't care whose model it is — it just
> calls the endpoint you name."

Then the IaC point:
> "The whole demo — the model, the Delta tables, the Lakebase instance, the app,
> the assistant — is one **Databricks Asset Bundle**. You clone the repo, set a
> handful of variables for your workspace, and deploy. It's a starting point you
> own and extend, not a product you rent."

---

## 5. Differentiator cheat-sheet (keep these one-liners ready)

- **"It's all in your workspace."** Model, analytics, operational DB, AI, and app —
  one governance boundary, one bill, no data egress.
- **"Delta for analytics, Lakebase for operations."** The right storage for each
  access pattern, both governed by Unity Catalog.
- **"Live serving, swappable in one line."** Demonstrates real Model Serving, not a
  mock; `serving_endpoint_name` swaps in their model.
- **"Transparent AI."** The assistant shows its SQL and sources and runs as the
  user — trustworthy by construction.
- **"Cloneable IaC."** A DABs bundle; deploy to any of their Azure Databricks
  workspaces with a few CLI commands.
- **"Modern app stack."** React + Vite + TypeScript + Tailwind + FastAPI, served
  directly by Databricks Apps — no separate hosting to procure or secure.

---

## 6. Likely questions & crisp answers

- **"Is this our real data?"** → No — 100% synthetic (pharmacies, SKUs, sales,
  forecasts) so we can demo without access. Structure mirrors what you'd have.
- **"How do we use our own forecasting model?"** → Change `serving_endpoint_name`
  to your endpoint and redeploy. The app calls whatever endpoint you name; if it
  returns quantiles, the confidence band renders automatically.
- **"How is the forecast-accuracy number calculated?"** → Be transparent: in this
  demo it's an **illustrative placeholder** (a "1 − MAPE, rolling 30-day"–style
  figure), not a live calculation — the synthetic data has no forecast-vs-realized
  overlap to score against. In your environment this KPI comes straight from your
  own **model monitoring** (Lakehouse Monitoring / your MLOps metrics); the card is
  the place to surface it. One-liner if pressed: *"That accuracy figure is a
  placeholder for the demo — in production it's wired to your model's monitored
  accuracy."*
- **"Does the model use ~30 days of history to predict the next 28 days?"** → Two
  parts. The **28-day horizon is real** (the app requests a 28-day forecast). But
  the *demo* model is a lightweight **deterministic seasonal** stand-in — it takes
  `pharmacy_id`, `product_id`, and `horizon` and computes expected demand from the
  date's weekly/seasonal pattern; it does **not** consume a history window. The
  "30 days" you see on the Overview is just the trend chart's display window (the
  detail page shows 90 days; we generate ~18 months of history). **Your** real
  model decides its own history window and features — the app only depends on the
  endpoint contract (send ids + horizon → get per-day p10/p50/p90), so nothing in
  the app changes when you swap it in.
- **"How is the Recommended reorder quantity calculated?"** → Simple two-week
  cover formula: **`max(0, demand_7d × 2 − on_hand)`**. Take the 7-day forecast
  demand, double it to set a 14-day cover target, subtract current stock on hand,
  and floor at zero (never recommend a negative order). It only appears for
  `critical` or `warning` products — healthy products with adequate stock show no
  recommendation. In live mode, if a supply-chain user has already logged a
  decision on the Reorders page, that stored figure is used instead of the
  formula. One-liner if asked: *"Target cover is 2 weeks in this demo — easily
  configurable per SKU, banner, or category based on Galenica's replenishment
  policy."*
- **"What do Forecast (p50) and the 80% interval mean on the chart?"** →
  **p50** is the model's median (50th-percentile) estimate — the central
  forecast line. The **80% interval** is the shaded band from p10 (10th
  percentile) to p90 (90th percentile): there is an 80% probability actual
  demand falls inside the band, with roughly 10% chance each of coming in below
  or above it. The band widens further into the future (more uncertainty at day
  28 than day 1). One-liner: *"The line is best estimate; the band is
  confidence — the wider it is, the more safety stock you'd want to carry."*
- **"How are 'critical' and 'warning' thresholds defined?"** → Both are based
  purely on **days of cover** — how many days the current stock will last at
  the forecast daily run rate (`on_hand ÷ daily_demand`):

  | Severity | Condition | Meaning |
  |---|---|---|
  | **Critical** | days cover **< 2** | Imminent stockout within 2 days |
  | **Warning** | days cover **2 – 4** | Stockout within days if not restocked |
  | **Overstock** | days cover **> 60** | Excess capital tied up in stock |
  | *(healthy)* | 4 – 60 days | No alert generated |

  One-liner if asked: *"2 days for critical, 4 for warning — hardcoded in this
  demo, but in production these would be configured per SKU category or banner.
  A prescription drug and a seasonal OTC product have very different acceptable
  cover levels."*
- **"What is Lakebase and why not just Delta?"** → Lakebase is managed Postgres
  inside Databricks for transactional, low-latency app state (acknowledgements,
  reorder decisions, notes). Delta is your analytical source of truth. The app uses
  both. Both are governed together.
- **"Who can see/do what?"** → The app authenticates users via SSO; the signed-in
  identity is shown and attached to write-backs. Access to tables, the endpoint,
  and the database is governed by Unity Catalog and resource permissions.
- **"Does the AI send our data anywhere?"** → No. It calls a Databricks Foundation
  Model endpoint in-platform; the query runs against your governed tables and the
  generated SQL is shown for verification.
- **"How hard is it to stand up in our environment?"** → It's a Databricks Asset
  Bundle. Clone → set variables → `bundle deploy` → run the setup job → deploy the
  app. See `README.md` for the exact phased steps.
- **"Can we extend/customize it?"** → Yes — it's your repo. Add pages, KPIs, new
  write-back tables, more Foundation Model features. Standard React/FastAPI.
- **"What about scale — 400+ sites, many SKUs?"** → Analytics run on a SQL
  Warehouse; operational reads/writes on Lakebase; tables are server-side
  paginated. Scales with the warehouse/instance you size.

---

## 7. Reset between demos (if you've been clicking around)

Acknowledging alerts and deciding reorders mutate Lakebase, so a second demo may
show fewer open items. To restore a fresh, "full worklist" state, re-run the seed
step of the setup job:

```bash
databricks bundle run forecasting_job -t dev -p galenica-eu
```

(That regenerates the synthetic data and re-seeds Lakebase. Only needed if the
operational tables have drifted from a lot of clicking.)

---

## 8. Timing variants

**5-minute flyby** (exec / hallway):
Overview → Network map (zoom once) → one Pharmacy detail (forecast band + a note
write-back) → the `serving_endpoint_name` swap line. Skip Alerts and Assistant.

**15-minute core:** Sections 4.0 → 4.6 as written above.

**30-minute technical deep-dive:** add, after the core —
- Open `resources/` and walk the bundle: `forecasting_job.job.yml` (data + model +
  seed), `app.app.yml` (resource bindings: SQL warehouse, Lakebase, both serving
  endpoints), the Lakebase database instance.
- Show `server/warehouse.py` (SDK Statement Execution), `server/db.py` (Lakebase
  OAuth connection pool), `server/serving.py` (the endpoint call), `server/llm.py`
  (Foundation Model).
- Walk the phased first-time deploy and the app-SP grant in `README.md`.
- Offer to swap `serving_endpoint_name` to a placeholder and redeploy live to prove
  the one-line swap.

---

## 9. One-line close

> "You bring the model and the data governance you already have on Azure Databricks.
> This is the last mile — a governed, cloneable app that puts your forecasts in
> front of the people who act on them. Clone it, point it at your endpoint, and make
> it yours."
