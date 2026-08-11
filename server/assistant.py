"""'Ask your data' assistant.

LIVE mode: sends a compact, factual context (current KPIs + top risks, computed
from the real data) to a Foundation Model via AI Gateway, so answers are grounded
in the actual numbers rather than the model's imagination.

MOCK mode: returns a grounded, templated answer built from the same in-process
figures — so the assistant is fully demoable offline.

Both modes surface a representative SQL query for transparency (the app-design
"show how the answer was computed" principle) and a source list.
"""
from . import repository
from .config import CATALOG, SCHEMA, use_mock

SCHEMA_DOC = f"""
Tables (Unity Catalog `{CATALOG}.{SCHEMA}`):
- dim_pharmacy(pharmacy_id, name, banner, canton_code, canton_name, latitude, longitude, size_factor)
- dim_product(product_id, name, category, ingredient, is_rx, seasonal_peak_month, unit_price_chf)
- fact_sales_daily(pharmacy_id, product_id, sale_date, units_sold)
- fact_forecast(pharmacy_id, product_id, forecast_date, forecast_p10, forecast_p50, forecast_p90)
Operational store (Lakebase `app`): stockout_alerts, reorder_decisions, annotations.
""".strip()


def _context() -> dict:
    ov = repository.get_overview()
    k = ov["kpis"]
    top = ov.get("top_risk_pharmacies", [])[:5]
    return {"kpis": k, "top_risk": top}


def _representative_sql(question: str) -> str:
    q = question.lower()
    if "stockout" in q or "risk" in q or "reorder" in q:
        return (
            f"SELECT a.pharmacy_id, p.name, a.severity, a.days_cover\n"
            f"FROM app.stockout_alerts a\n"
            f"JOIN {CATALOG}.{SCHEMA}.dim_pharmacy p USING (pharmacy_id)\n"
            f"WHERE a.status = 'open' AND a.severity IN ('critical','warning')\n"
            f"ORDER BY a.days_cover ASC LIMIT 20;"
        )
    if "canton" in q or "region" in q:
        return (
            f"SELECT p.canton_name, SUM(f.forecast_p50) AS demand_7d\n"
            f"FROM {CATALOG}.{SCHEMA}.fact_forecast f\n"
            f"JOIN {CATALOG}.{SCHEMA}.dim_pharmacy p USING (pharmacy_id)\n"
            f"WHERE f.forecast_date < date_add(current_date(), 7)\n"
            f"GROUP BY p.canton_name ORDER BY demand_7d DESC;"
        )
    return (
        f"SELECT SUM(forecast_p50) AS demand_7d\n"
        f"FROM {CATALOG}.{SCHEMA}.fact_forecast\n"
        f"WHERE forecast_date < date_add(current_date(), 7);"
    )


def _mock_answer(question: str, ctx: dict) -> str:
    k = ctx["kpis"]
    top = ctx["top_risk"]
    q = question.lower()
    if "stockout" in q or "risk" in q or "reorder" in q:
        lines = [
            f"There are **{k['critical_alerts']} critical** and **{k['warning_alerts']} warning** "
            f"stockout alerts across {k['pharmacies_at_risk']} pharmacies. The highest-risk sites are:"
        ]
        for p in top:
            lines.append(f"- {p['name']} ({p['canton_code']}) — {p['critical_alerts']} critical, "
                         f"{p['warning_alerts']} warning")
        lines.append("\nRecommend prioritising reorders for the critical sites within the next 48h.")
        return "\n".join(lines)
    if "canton" in q or "region" in q:
        return (f"Forecast demand over the next 7 days totals ~{k['forecast_demand_7d']:,} units "
                f"network-wide. Demand concentrates in the populous cantons (Zürich, Bern, Vaud). "
                f"Open the Swiss map view to see per-canton risk shading.")
    return (
        f"Network 7-day forecast demand is ~{k['forecast_demand_7d']:,} units across "
        f"{k['total_pharmacies']} pharmacies and {k['total_products']} SKUs. Model forecast "
        f"accuracy is ~{k['forecast_accuracy_pct']}%. There are {k['critical_alerts']} critical "
        f"stockout alerts to action."
    )


def answer_question(question: str) -> dict:
    ctx = _context()
    sql = _representative_sql(question)
    sources = [f"{CATALOG}.{SCHEMA}.fact_forecast", "app.stockout_alerts",
               f"{CATALOG}.{SCHEMA}.dim_pharmacy"]
    if use_mock():
        return {"answer": _mock_answer(question, ctx), "sql": sql,
                "sources": sources, "source": "mock"}

    from .llm import chat_completion
    system = (
        "You are the Galenica demand-forecasting assistant. Answer concisely (<120 words) "
        "using ONLY the provided figures. Be specific with numbers. If the question can't be "
        "answered from the context, say what data would be needed.\n\n"
        + SCHEMA_DOC
        + f"\n\nCurrent figures (JSON): {ctx}"
    )
    try:
        answer = chat_completion(
            [{"role": "system", "content": system},
             {"role": "user", "content": question}]
        )
        source = "foundation-model"
    except Exception as e:
        answer = _mock_answer(question, ctx) + f"\n\n_(LLM unavailable: {e})_"
        source = "fallback"
    return {"answer": answer, "sql": sql, "sources": sources, "source": source}
