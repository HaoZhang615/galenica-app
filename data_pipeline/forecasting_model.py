"""Synthetic demand-forecasting pyfunc model for the Galenica demo.

This stands in for Galenica's real trained forecasting models. It is a genuine
MLflow pyfunc that gets registered in Unity Catalog and deployed to a real Model
Serving endpoint — so the app demonstrates *live* endpoint serving, not a mock.

The model bakes in a small per-series lookup (pharmacy x product baseline +
seasonal peak) as an artifact, so callers only send `pharmacy_id`, `product_id`
and a `horizon`. It returns a smooth expected forecast (p50) with p10/p90 bands.

To swap in Galenica's production model, point the app's SERVING_ENDPOINT at their
endpoint name — the request/response contract below is all the app depends on.

Request (any of the MLflow serving input formats), one row per series:
    {"dataframe_records": [{"pharmacy_id": "PH0001", "product_id": "SKU0007", "horizon": 28}]}

Response: one object per input row:
    [{"pharmacy_id": "PH0001", "product_id": "SKU0007",
      "forecast": [{"day": 0, "date": "2026-08-11", "p10": .., "p50": .., "p90": ..}, ...]}]
"""
import datetime as dt
import json
import math
import os

import mlflow.pyfunc

TWO_PI_OVER_YEAR = 2 * math.pi / 365.0


class GalenicaForecastModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        with open(context.artifacts["series"], "r") as f:
            # keys are "pharmacy_id|product_id" -> [series_base, seasonal_peak_month]
            self.series = json.load(f)

    # -- shared demand curve (deterministic expected value; no random noise) ----
    @staticmethod
    def _weekly(date: dt.date) -> float:
        # Python weekday(): Mon=0 .. Sun=6
        wd = date.weekday()
        if wd == 6:      # Sunday
            return 0.45
        if wd == 5:      # Saturday
            return 1.15
        if wd in (3, 4):  # Thu, Fri
            return 1.20
        return 1.0

    @classmethod
    def _expected(cls, base: float, date: dt.date, peak_month: int) -> float:
        doy = date.timetuple().tm_yday
        if peak_month == 0:
            annual = 1.0
        else:
            peak_doy = (peak_month - 1) * 30.4 + 15
            annual = 1.0 + 0.6 * math.cos(TWO_PI_OVER_YEAR * (doy - peak_doy))
        winter = 1.0 + 0.10 * math.cos(TWO_PI_OVER_YEAR * (doy - 15))
        return max(0.0, base * cls._weekly(date) * annual * winter)

    def _forecast_series(self, pharmacy_id: str, product_id: str, horizon: int, start: dt.date):
        key = f"{pharmacy_id}|{product_id}"
        base, peak = self.series.get(key, [8.0, 0])
        out = []
        for d in range(horizon):
            date = start + dt.timedelta(days=d)
            p50 = self._expected(base, date, int(peak))
            rel_sigma = 0.12 + 0.010 * d
            p10 = max(0.0, p50 * (1.0 - 1.2816 * rel_sigma))
            p90 = p50 * (1.0 + 1.2816 * rel_sigma)
            out.append({
                "day": d, "date": date.isoformat(),
                "p10": round(p10, 1), "p50": round(p50, 1), "p90": round(p90, 1),
            })
        return out

    def predict(self, context, model_input, params=None):
        # model_input is a pandas DataFrame (MLflow serving convention).
        start = dt.date.today()
        results = []
        for _, row in model_input.iterrows():
            pharmacy_id = str(row.get("pharmacy_id", ""))
            product_id = str(row.get("product_id", ""))
            horizon = int(row.get("horizon", 28) or 28)
            horizon = max(1, min(horizon, 90))
            results.append({
                "pharmacy_id": pharmacy_id,
                "product_id": product_id,
                "forecast": self._forecast_series(pharmacy_id, product_id, horizon, start),
            })
        return results
