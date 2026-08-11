"""FastAPI entry point for the Galenica demand-forecasting demo.

Serves the JSON API under /api and the built React SPA for everything else.
In LIVE mode the Lakebase pool is opened at startup; in MOCK mode there is no
external dependency, so the app runs anywhere with just `uvicorn app:app`.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.config import use_mock
from server.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not use_mock():
        from server.db import close_pool, open_pool
        open_pool()
        try:
            yield
        finally:
            close_pool()
    else:
        yield


app = FastAPI(title="Galenica Demand Forecasting", lifespan=lifespan)
app.include_router(api_router, prefix="/api")


@app.get("/healthz")
def healthz():
    return JSONResponse({"status": "ok", "mode": "mock" if use_mock() else "live"})


# --- serve the built React frontend ----------------------------------------
_frontend = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        # API 404s should not fall through to index.html.
        if full_path.startswith("api/"):
            return JSONResponse({"error": "not_found"}, status_code=404)
        index = os.path.join(_frontend, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return JSONResponse({"error": "frontend not built"}, status_code=404)
