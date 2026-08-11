"""HTTP API for the Galenica demo. Mounted under /api by app.py."""
import datetime as dt

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from . import repository
from .assistant import answer_question
from .config import CATALOG, SCHEMA, SERVING_ENDPOINT, use_mock

router = APIRouter()


# --- identity ---------------------------------------------------------------
def _current_user(request: Request) -> str:
    # Databricks Apps inject the signed-in user via these headers.
    return (
        request.headers.get("x-forwarded-email")
        or request.headers.get("x-forwarded-user")
        or ("demo.user@galenica.ch" if use_mock() else "app-service-principal")
    )


@router.get("/whoami")
def whoami(request: Request):
    return {
        "user": _current_user(request),
        "mode": "mock" if use_mock() else "live",
        "catalog": CATALOG,
        "schema": SCHEMA,
        "serving_endpoint": SERVING_ENDPOINT,
    }


@router.get("/overview")
def overview():
    return repository.get_overview()


@router.get("/pharmacies")
def pharmacies():
    return {"rows": repository.get_pharmacies()}


@router.get("/pharmacies/{pharmacy_id}")
def pharmacy_detail(pharmacy_id: str):
    data = repository.get_pharmacy(pharmacy_id)
    if not data:
        return {"error": "not_found"}
    data["annotations"] = repository.get_annotations(pharmacy_id)
    return data


@router.get("/forecast")
def forecast(
    pharmacy_id: str,
    product_id: str,
    horizon: int = Query(28, ge=1, le=90),
    history_days: int = Query(90, ge=7, le=545),
):
    return repository.get_product_forecast(pharmacy_id, product_id, horizon, history_days)


@router.get("/alerts")
def alerts(
    status: str = "open",
    severity: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    return repository.get_alerts(status, severity, page, page_size)


class AckBody(BaseModel):
    pass


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int, request: Request):
    return repository.acknowledge_alert(alert_id, _current_user(request))


@router.get("/reorders")
def reorders(status: str = "pending"):
    return {"rows": repository.get_reorders(status)}


class ReorderDecision(BaseModel):
    decided_qty: int
    status: str = "approved"  # 'approved' | 'rejected'


@router.post("/reorders/{reorder_id}/decide")
def decide_reorder(reorder_id: int, body: ReorderDecision, request: Request):
    return repository.decide_reorder(reorder_id, body.decided_qty, body.status, _current_user(request))


class AnnotationBody(BaseModel):
    product_id: str | None = None
    note: str


@router.post("/pharmacies/{pharmacy_id}/annotations")
def add_annotation(pharmacy_id: str, body: AnnotationBody, request: Request):
    return repository.add_annotation(pharmacy_id, body.product_id, body.note, _current_user(request))


class AssistantBody(BaseModel):
    question: str


@router.post("/assistant")
def assistant(body: AssistantBody, request: Request):
    result = answer_question(body.question)
    result["user"] = _current_user(request)
    result["disclaimer"] = "AI-generated — verify against source data before acting."
    return result
