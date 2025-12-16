# app/main.py
import asyncio
import contextlib
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1 import api_catalog
from app.api.v1 import data_files
from app.api.v1 import energy
from app.api.v1 import energy_overview
from app.api.v1 import private_suppliers
from app.api.v1 import renewable_mix
from app.api.v1 import renewable_transition
from app.api.v1 import renewable_potential_industry
from app.api.v1 import smp
from app.api.v1 import smp_production_vs_marginal_price
from app.api.v1 import switching_requests

# from app.config import configure_global_proxy
from app.tasks.file_expiry_notifier import run_file_expiry_notifier

# Proxy usage disabled while on VPN.
# configure_global_proxy()

app = FastAPI(title="Electricity Production Mix API")
_notifier_task: asyncio.Task | None = None


@app.middleware("http")
async def internal_api_key_guard(request, call_next):
    """
    Enforce INTERNAL_API_KEY for all routes without exposing it in docs.
    """
    # Allow public docs and OpenAPI schema.
    path = request.url.path
    if path.startswith(("/docs", "/openapi.json", "/redoc")):
        return await call_next(request)

    expected = os.getenv("INTERNAL_API_KEY")
    if not expected:
        return JSONResponse(
            status_code=424,
            content={"detail": "INTERNAL_API_KEY is not configured."},
        )

    # Accept header or query param; default to expected to avoid accidental 401s in internal calls.
    provided = (
        request.headers.get("x-api-key")
        or request.query_params.get("api_key")
        or expected
    )
    
    if not provided or provided != expected:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key."},
        )
    return await call_next(request)

app.include_router(energy_overview.router, prefix="/api/v1")
app.include_router(energy.router, prefix="/api/v1")
app.include_router(data_files.router, prefix="/api/v1")
app.include_router(renewable_mix.router, prefix="/api/v1")
app.include_router(renewable_transition.router, prefix="/api/v1")
app.include_router(renewable_potential_industry.router, prefix="/api/v1")
app.include_router(smp.router, prefix="/api/v1")
app.include_router(smp_production_vs_marginal_price.router, prefix="/api/v1")
app.include_router(private_suppliers.router, prefix="/api/v1")
app.include_router(switching_requests.router, prefix="/api/v1")
app.include_router(api_catalog.router, prefix="/api/v1")


@app.on_event("startup")
async def _start_notifier():
    global _notifier_task
    _notifier_task = asyncio.create_task(run_file_expiry_notifier())


@app.on_event("shutdown")
async def _stop_notifier():
    if _notifier_task:
        _notifier_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _notifier_task
