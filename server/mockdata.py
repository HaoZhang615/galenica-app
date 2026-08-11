"""In-process synthetic data for MOCK mode.

Mirrors the Delta/Spark generator (data_pipeline/generate_synthetic_data.py) in
pure Python so the app is fully demoable with no Databricks connection. The
demand curve matches the served pyfunc model, so forecasts look consistent
whether they come from here or from the live endpoint.

All data is deterministic (seeded) so it's stable across restarts.
"""
import datetime as dt
import functools
import math
import random

TWO_PI_OVER_YEAR = 2 * math.pi / 365.0
SEED = 42
N_PHARMACIES = 420

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
BANNERS = ["Amavita", "Sun Store", "Coop Vitality"]

CATEGORIES = [
    ("Analgesics", False, 0, 8), ("Cold & Flu", False, 1, 8),
    ("Allergy", False, 4, 6), ("Vitamins & Supplements", False, 11, 8),
    ("Dermatology", False, 7, 5), ("Digestive Health", False, 0, 5),
    ("Cardiovascular", True, 0, 6), ("Diabetes", True, 0, 5),
    ("Antibiotics", True, 2, 5), ("Respiratory", True, 12, 5),
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


# --- demand curve (matches the served model's expected value) -----------------
def _weekly(date: dt.date) -> float:
    wd = date.weekday()  # Mon=0 .. Sun=6
    if wd == 6:
        return 0.45
    if wd == 5:
        return 1.15
    if wd in (3, 4):
        return 1.20
    return 1.0


def expected_demand(base: float, date: dt.date, peak_month: int) -> float:
    doy = date.timetuple().tm_yday
    if peak_month == 0:
        annual = 1.0
    else:
        peak_doy = (peak_month - 1) * 30.4 + 15
        annual = 1.0 + 0.6 * math.cos(TWO_PI_OVER_YEAR * (doy - peak_doy))
    winter = 1.0 + 0.10 * math.cos(TWO_PI_OVER_YEAR * (doy - 15))
    return max(0.0, base * _weekly(date) * annual * winter)


@functools.lru_cache(maxsize=1)
def pharmacies() -> list:
    rng = random.Random(SEED)
    total_w = sum(c[4] for c in CANTONS)
    out = []
    for i in range(1, N_PHARMACIES + 1):
        r = rng.uniform(0, total_w)
        acc, canton = 0.0, CANTONS[0]
        for c in CANTONS:
            acc += c[4]
            if r <= acc:
                canton = c
                break
        code, name, lat, lon, _ = canton
        banner = BANNERS[rng.randrange(len(BANNERS))]
        out.append({
            "pharmacy_id": f"PH{i:04d}",
            "name": f"{banner} {name} {i:04d}",
            "banner": banner,
            "canton_code": code,
            "canton_name": name,
            "city": name,
            "latitude": round(lat + rng.uniform(-0.18, 0.18), 5),
            "longitude": round(lon + rng.uniform(-0.25, 0.25), 5),
            "size_factor": round(rng.uniform(0.55, 1.9), 3),
        })
    return out


@functools.lru_cache(maxsize=1)
def products() -> list:
    rng = random.Random(SEED + 1)
    out, pid = [], 0
    for category, is_rx, peak_month, n in CATEGORIES:
        ings = INGREDIENTS[category]
        for _ in range(n):
            pid += 1
            ing = ings[rng.randrange(len(ings))]
            form = FORMS[rng.randrange(len(FORMS))]
            strength = STRENGTHS[rng.randrange(len(STRENGTHS))]
            out.append({
                "product_id": f"SKU{pid:04d}",
                "name": f"{ing} {strength} {form}",
                "category": category,
                "ingredient": ing,
                "form": form,
                "strength": strength,
                "is_rx": is_rx,
                "seasonal_peak_month": peak_month,
                "base_popularity": round(rng.uniform(3.0, 22.0) * (0.7 if is_rx else 1.2), 2),
                "unit_price_chf": round(rng.uniform(4.0, 45.0) * (1.6 if is_rx else 1.0), 2),
            })
    return out


@functools.lru_cache(maxsize=1)
def _index():
    ph = {p["pharmacy_id"]: p for p in pharmacies()}
    pr = {p["product_id"]: p for p in products()}
    return ph, pr


def series_base(pharmacy_id: str, product_id: str) -> tuple:
    ph, pr = _index()
    p = ph.get(pharmacy_id)
    q = pr.get(product_id)
    if not p or not q:
        return 8.0, 0
    return p["size_factor"] * q["base_popularity"], q["seasonal_peak_month"]


def forecast_series(pharmacy_id: str, product_id: str, horizon: int = 28,
                    start: dt.date = None) -> list:
    """p10/p50/p90 forecast for a series (same shape as the served model)."""
    start = start or dt.date.today()
    base, peak = series_base(pharmacy_id, product_id)
    out = []
    for d in range(horizon):
        date = start + dt.timedelta(days=d)
        p50 = expected_demand(base, date, peak)
        rel_sigma = 0.12 + 0.010 * d
        p10 = max(0.0, p50 * (1.0 - 1.2816 * rel_sigma))
        p90 = p50 * (1.0 + 1.2816 * rel_sigma)
        out.append({"day": d, "date": date.isoformat(),
                    "p10": round(p10, 1), "p50": round(p50, 1), "p90": round(p90, 1)})
    return out


def actuals_series(pharmacy_id: str, product_id: str, history_days: int = 90,
                   end: dt.date = None) -> list:
    """Historical units with realistic noise (deterministic per series/day)."""
    end = end or dt.date.today()
    base, peak = series_base(pharmacy_id, product_id)
    rng = random.Random(hash((pharmacy_id, product_id)) & 0xFFFFFFFF)
    out = []
    for d in range(history_days, 0, -1):
        date = end - dt.timedelta(days=d)
        exp = expected_demand(base, date, peak)
        promo = 1.8 if rng.random() < 0.04 else 1.0
        noise = 0.75 + rng.random() * 0.5
        out.append({"date": date.isoformat(), "units": max(0, round(exp * promo * noise))})
    return out


# --- derived aggregates (cached) ----------------------------------------------
@functools.lru_cache(maxsize=1)
def _series_risk() -> list:
    """Per-series 7-day demand, synthetic on-hand, days-of-cover + severity."""
    today = dt.date.today()
    days = [today + dt.timedelta(days=i) for i in range(7)]
    rng = random.Random(SEED + 3)
    rows = []
    for p in pharmacies():
        for q in products():
            base = p["size_factor"] * q["base_popularity"]
            demand_7d = sum(expected_demand(base, d, q["seasonal_peak_month"]) for d in days)
            # target days-of-cover ~ log-normal (median ~12d): most stores healthy,
            # with a critical/warning tail and an occasional overstock.
            target_cover = math.exp(math.log(12.0) + rng.gauss(0, 0.8))
            daily = demand_7d / 7 + 0.001
            on_hand = max(0, int(round(target_cover * daily)))
            days_cover = on_hand / daily
            severity = None
            if days_cover < 2:
                severity = "critical"
            elif days_cover < 4:
                severity = "warning"
            elif days_cover > 60:
                severity = "overstock"
            rows.append({
                "pharmacy_id": p["pharmacy_id"], "product_id": q["product_id"],
                "demand_7d": round(demand_7d, 1), "on_hand": on_hand,
                "days_cover": round(days_cover, 2), "severity": severity,
            })
    return rows


@functools.lru_cache(maxsize=1)
def alerts() -> list:
    rows = [r for r in _series_risk() if r["severity"]]
    # stable ordering: critical first, then by days_cover
    order = {"critical": 0, "warning": 1, "overstock": 2}
    rows.sort(key=lambda r: (order[r["severity"]], r["days_cover"]))
    ph, pr = _index()
    for i, r in enumerate(rows, 1):
        r["id"] = i
        r["status"] = "open"
        r["pharmacy_name"] = ph[r["pharmacy_id"]]["name"]
        r["product_name"] = pr[r["product_id"]]["name"]
        r["canton_code"] = ph[r["pharmacy_id"]]["canton_code"]
    return rows
