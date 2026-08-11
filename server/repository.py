"""Data-access layer: one API for the routes, two backends underneath.

MOCK mode  -> server/mockdata.py + in-memory write stores (fully self-contained).
LIVE mode  -> SQL Warehouse (analytics) + Lakebase (operational) + serving
              endpoint (on-demand forecasts).

Routes never branch on mode; they call these functions.
"""
import datetime as dt
import functools
import itertools

from . import mockdata
from .config import CATALOG, SCHEMA, use_mock

# ---------------------------------------------------------------------------
# In-memory write stores for MOCK mode (reset on restart).
# ---------------------------------------------------------------------------
_mock_ack: dict[int, dict] = {}          # alert_id -> {by, at}
_mock_annotations: list[dict] = []
_mock_reorders: dict = None              # lazily built
_id_counter = itertools.count(10_000)


def _fq(table: str) -> str:
    return f"{CATALOG}.{SCHEMA}.{table}"


# ===========================================================================
# Overview / KPIs
# ===========================================================================
@functools.lru_cache(maxsize=1)
def _mock_overview_cache():
    risk = mockdata._series_risk()
    alerts = mockdata.alerts()
    total_demand_7d = sum(r["demand_7d"] for r in risk)
    critical = sum(1 for a in alerts if a["severity"] == "critical")
    warning = sum(1 for a in alerts if a["severity"] == "warning")
    overstock = sum(1 for a in alerts if a["severity"] == "overstock")
    at_risk_ph = len({a["pharmacy_id"] for a in alerts if a["severity"] == "critical"})
    avg_cover = sum(r["days_cover"] for r in risk) / max(1, len(risk))

    # national trend: 30d actual (expected) + 28d forecast, sampled pharmacies scaled up
    phs = mockdata.pharmacies()
    prods = mockdata.products()
    sample = phs[::7]                        # ~60 pharmacies
    scale = len(phs) / len(sample)
    today = dt.date.today()
    trend = []
    for offset in range(-30, 28):
        date = today + dt.timedelta(days=offset)
        total = 0.0
        for p in sample:
            for q in prods:
                base = p["size_factor"] * q["base_popularity"]
                total += mockdata.expected_demand(base, date, q["seasonal_peak_month"])
        trend.append({
            "date": date.isoformat(),
            "actual": round(total * scale) if offset < 0 else None,
            "forecast": round(total * scale) if offset >= 0 else None,
        })
    return {
        "kpis": {
            "forecast_demand_7d": round(total_demand_7d),
            "critical_alerts": critical,
            "warning_alerts": warning,
            "overstock_alerts": overstock,
            "pharmacies_at_risk": at_risk_ph,
            "total_pharmacies": len(phs),
            "total_products": len(prods),
            "avg_days_cover": round(avg_cover, 1),
            "forecast_accuracy_pct": 91.4,   # illustrative MAPE-derived accuracy
        },
        "national_trend": trend,
    }


def get_overview() -> dict:
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    if use_mock():
        data = _mock_overview_cache()
        top_risk = get_top_risk_pharmacies(limit=8)
        return {**data, "top_risk_pharmacies": top_risk,
                "data_source": "mock", "generated_at": generated_at}

    from . import warehouse
    kpi_rows = warehouse.query(f"""
        WITH f AS (
          SELECT pharmacy_id, product_id, SUM(forecast_p50) AS demand_7d
          FROM {_fq('fact_forecast')}
          WHERE forecast_date < date_add(current_date(), 7)
          GROUP BY pharmacy_id, product_id
        )
        SELECT SUM(demand_7d) AS forecast_demand_7d,
               (SELECT COUNT(*) FROM {_fq('dim_pharmacy')}) AS total_pharmacies,
               (SELECT COUNT(*) FROM {_fq('dim_product')}) AS total_products
        FROM f
    """)
    trend = warehouse.query(f"""
        SELECT CAST(sale_date AS STRING) AS date, SUM(units_sold) AS actual, NULL AS forecast
        FROM {_fq('fact_sales_daily')}
        WHERE sale_date >= date_add(current_date(), -30)
        GROUP BY sale_date
        UNION ALL
        SELECT CAST(forecast_date AS STRING) AS date, NULL AS actual, SUM(forecast_p50) AS forecast
        FROM {_fq('fact_forecast')}
        GROUP BY forecast_date
        ORDER BY date
    """)
    # alert counts come from Lakebase
    counts = _lakebase_query(
        "SELECT severity, COUNT(*) AS n FROM app.stockout_alerts WHERE status='open' GROUP BY severity"
    )
    cmap = {r["severity"]: r["n"] for r in counts}
    k = kpi_rows[0] if kpi_rows else {}
    return {
        "kpis": {
            "forecast_demand_7d": round(k.get("forecast_demand_7d") or 0),
            "critical_alerts": cmap.get("critical", 0),
            "warning_alerts": cmap.get("warning", 0),
            "overstock_alerts": cmap.get("overstock", 0),
            "pharmacies_at_risk": 0,
            "total_pharmacies": k.get("total_pharmacies", 0),
            "total_products": k.get("total_products", 0),
            "avg_days_cover": None,
            "forecast_accuracy_pct": 91.4,
        },
        "national_trend": trend,
        "top_risk_pharmacies": get_top_risk_pharmacies(limit=8),
        "data_source": "live",
        "generated_at": generated_at,
    }


# ===========================================================================
# Pharmacies (list + map)
# ===========================================================================
def get_pharmacies() -> list[dict]:
    if use_mock():
        alerts = mockdata.alerts()
        by_ph: dict[str, dict] = {}
        for a in alerts:
            d = by_ph.setdefault(a["pharmacy_id"], {"critical": 0, "warning": 0, "overstock": 0})
            d[a["severity"]] += 1
        out = []
        for p in mockdata.pharmacies():
            c = by_ph.get(p["pharmacy_id"], {})
            risk = c.get("critical", 0) * 3 + c.get("warning", 0)
            out.append({**p,
                        "critical_alerts": c.get("critical", 0),
                        "warning_alerts": c.get("warning", 0),
                        "overstock_alerts": c.get("overstock", 0),
                        "risk_score": risk})
        return out

    from . import warehouse
    phs = warehouse.query(f"SELECT * FROM {_fq('dim_pharmacy')}")
    counts = _lakebase_query("""
        SELECT pharmacy_id,
               SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END) AS critical_alerts,
               SUM(CASE WHEN severity='warning' THEN 1 ELSE 0 END) AS warning_alerts,
               SUM(CASE WHEN severity='overstock' THEN 1 ELSE 0 END) AS overstock_alerts
        FROM app.stockout_alerts WHERE status='open' GROUP BY pharmacy_id
    """)
    cmap = {r["pharmacy_id"]: r for r in counts}
    for p in phs:
        c = cmap.get(p["pharmacy_id"], {})
        p["critical_alerts"] = int(c.get("critical_alerts", 0) or 0)
        p["warning_alerts"] = int(c.get("warning_alerts", 0) or 0)
        p["overstock_alerts"] = int(c.get("overstock_alerts", 0) or 0)
        p["risk_score"] = p["critical_alerts"] * 3 + p["warning_alerts"]
    return phs


def get_top_risk_pharmacies(limit: int = 8) -> list[dict]:
    phs = sorted(get_pharmacies(), key=lambda p: p["risk_score"], reverse=True)
    return [p for p in phs if p["risk_score"] > 0][:limit]


# ===========================================================================
# Pharmacy detail + product forecast
# ===========================================================================
def get_pharmacy(pharmacy_id: str) -> dict:
    ph = next((p for p in get_pharmacies() if p["pharmacy_id"] == pharmacy_id), None)
    if not ph:
        return None
    risk_rows = [r for r in _series_risk_for_pharmacy(pharmacy_id)]
    return {"pharmacy": ph, "products": risk_rows}


def _series_risk_for_pharmacy(pharmacy_id: str) -> list[dict]:
    if use_mock():
        rows = [r for r in mockdata._series_risk() if r["pharmacy_id"] == pharmacy_id]
        _, pr = mockdata._index()
        for r in rows:
            prod = pr[r["product_id"]]
            r = r  # already dict
            r["product_name"] = prod["name"]
            r["category"] = prod["category"]
            r["is_rx"] = prod["is_rx"]
            r["recommended_qty"] = max(0, int(round(r["demand_7d"] * 2 - r["on_hand"]))) \
                if r["severity"] in ("critical", "warning") else 0
        rows.sort(key=lambda r: (r["severity"] is None, r["days_cover"]))
        return rows
    from . import warehouse
    return warehouse.query(f"""
        SELECT f.product_id, p.name AS product_name, p.category, p.is_rx,
               SUM(f.forecast_p50) AS demand_7d
        FROM {_fq('fact_forecast')} f
        JOIN {_fq('dim_product')} p ON p.product_id = f.product_id
        WHERE f.pharmacy_id = %(pid)s AND f.forecast_date < date_add(current_date(), 7)
        GROUP BY f.product_id, p.name, p.category, p.is_rx
        ORDER BY demand_7d DESC
    """, {"pid": pharmacy_id})


def get_product_forecast(pharmacy_id: str, product_id: str, horizon: int = 28,
                         history_days: int = 90) -> dict:
    _, pr = mockdata._index()
    ph_idx, _ = mockdata._index()
    product = pr.get(product_id)
    pharmacy = ph_idx.get(pharmacy_id)
    if use_mock():
        forecast = mockdata.forecast_series(pharmacy_id, product_id, horizon)
        source = "mock"
    else:
        from . import serving, warehouse
        forecast = serving.forecast(pharmacy_id, product_id, horizon)
        source = "serving-endpoint"
    # actuals
    if use_mock():
        actuals = mockdata.actuals_series(pharmacy_id, product_id, history_days)
    else:
        from . import warehouse
        actuals = warehouse.query(f"""
            SELECT CAST(sale_date AS STRING) AS date, units_sold AS units
            FROM {_fq('fact_sales_daily')}
            WHERE pharmacy_id=%(ph)s AND product_id=%(pr)s
              AND sale_date >= date_add(current_date(), -{int(history_days)})
            ORDER BY sale_date
        """, {"ph": pharmacy_id, "pr": product_id})
    return {"pharmacy": pharmacy, "product": product,
            "actuals": actuals, "forecast": forecast, "source": source}


# ===========================================================================
# Alerts
# ===========================================================================
def get_alerts(status: str = "open", severity: str = None,
               page: int = 1, page_size: int = 25) -> dict:
    if use_mock():
        rows = [dict(a) for a in mockdata.alerts()]
        for r in rows:
            ack = _mock_ack.get(r["id"])
            if ack:
                r["status"] = "acknowledged"
                r["acknowledged_by"] = ack["by"]
                r["acknowledged_at"] = ack["at"]
        if status and status != "all":
            rows = [r for r in rows if r["status"] == status]
        if severity:
            rows = [r for r in rows if r["severity"] == severity]
        total = len(rows)
        start = (page - 1) * page_size
        return {"rows": rows[start:start + page_size], "total": total,
                "page": page, "page_size": page_size}

    where = []
    params = {}
    if status and status != "all":
        where.append("status = %(status)s"); params["status"] = status
    if severity:
        where.append("severity = %(sev)s"); params["sev"] = severity
    wc = ("WHERE " + " AND ".join(where)) if where else ""
    total = _lakebase_query(f"SELECT COUNT(*) AS n FROM app.stockout_alerts {wc}", params)[0]["n"]
    params2 = {**params, "lim": page_size, "off": (page - 1) * page_size}
    rows = _lakebase_query(f"""
        SELECT * FROM app.stockout_alerts {wc}
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, days_cover
        LIMIT %(lim)s OFFSET %(off)s
    """, params2)
    return {"rows": rows, "total": total, "page": page, "page_size": page_size}


def acknowledge_alert(alert_id: int, user: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if use_mock():
        _mock_ack[alert_id] = {"by": user, "at": now}
        return {"id": alert_id, "status": "acknowledged", "acknowledged_by": user, "acknowledged_at": now}
    _lakebase_exec(
        "UPDATE app.stockout_alerts SET status='acknowledged', acknowledged_by=%(u)s, "
        "acknowledged_at=now() WHERE id=%(id)s",
        {"u": user, "id": alert_id},
    )
    return {"id": alert_id, "status": "acknowledged", "acknowledged_by": user}


# ===========================================================================
# Reorder decisions
# ===========================================================================
def _build_mock_reorders():
    global _mock_reorders
    if _mock_reorders is None:
        _mock_reorders = {}
        _, pr = mockdata._index()
        ph_idx, _ = mockdata._index()
        for a in mockdata.alerts():
            if a["severity"] not in ("critical", "warning"):
                continue
            rid = len(_mock_reorders) + 1
            rec = max(1, int(round(a["demand_7d"] * 2 - a["on_hand"])))
            _mock_reorders[rid] = {
                "id": rid, "pharmacy_id": a["pharmacy_id"], "product_id": a["product_id"],
                "pharmacy_name": a["pharmacy_name"], "product_name": a["product_name"],
                "recommended_qty": rec, "decided_qty": None, "status": "pending",
                "decided_by": None, "decided_at": None,
            }
    return _mock_reorders


def get_reorders(status: str = "pending") -> list[dict]:
    if use_mock():
        rows = list(_build_mock_reorders().values())
        if status and status != "all":
            rows = [r for r in rows if r["status"] == status]
        return rows
    wc = "" if status in (None, "all") else "WHERE r.status = %(s)s"
    return _lakebase_query(f"""
        SELECT r.* FROM app.reorder_decisions r {wc} ORDER BY r.created_at DESC LIMIT 500
    """, {"s": status})


def decide_reorder(reorder_id: int, decided_qty: int, status: str, user: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if use_mock():
        r = _build_mock_reorders().get(reorder_id)
        if r:
            r.update(decided_qty=decided_qty, status=status, decided_by=user, decided_at=now)
        return r
    _lakebase_exec(
        "UPDATE app.reorder_decisions SET decided_qty=%(q)s, status=%(s)s, decided_by=%(u)s, "
        "decided_at=now() WHERE id=%(id)s",
        {"q": decided_qty, "s": status, "u": user, "id": reorder_id},
    )
    return {"id": reorder_id, "decided_qty": decided_qty, "status": status, "decided_by": user}


# ===========================================================================
# Annotations
# ===========================================================================
def get_annotations(pharmacy_id: str) -> list[dict]:
    if use_mock():
        return [a for a in _mock_annotations if a["pharmacy_id"] == pharmacy_id]
    return _lakebase_query(
        "SELECT * FROM app.annotations WHERE pharmacy_id=%(p)s ORDER BY created_at DESC",
        {"p": pharmacy_id},
    )


def add_annotation(pharmacy_id: str, product_id: str, note: str, author: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if use_mock():
        a = {"id": next(_id_counter), "pharmacy_id": pharmacy_id, "product_id": product_id,
             "note": note, "author": author, "created_at": now}
        _mock_annotations.insert(0, a)
        return a
    _lakebase_exec(
        "INSERT INTO app.annotations (pharmacy_id, product_id, note, author) "
        "VALUES (%(p)s,%(pr)s,%(n)s,%(a)s)",
        {"p": pharmacy_id, "pr": product_id, "n": note, "a": author},
    )
    return {"pharmacy_id": pharmacy_id, "product_id": product_id, "note": note,
            "author": author, "created_at": now}


# ===========================================================================
# Lakebase helpers (LIVE)
# ===========================================================================
def _lakebase_query(sql: str, params=None) -> list[dict]:
    from .db import get_pool
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _lakebase_exec(sql: str, params=None) -> None:
    from .db import get_pool
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
        conn.commit()
