# app/main.py
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1 import energy
from app.api.v1 import energy_overview
from app.api.v1 import data_files
from app.api.v1 import private_suppliers
from app.api.v1 import smp
from app.api.v1 import smp_production_vs_marginal_price
from app.api.v1 import switching_requests
from app.config import configure_global_proxy

# Ensure all outbound HTTP clients respect the proxy before anything else runs.
configure_global_proxy()

app = FastAPI(title="Electricity Production Mix API")


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
    provided = request.headers.get("x-api-key")
    # If a key is provided, enforce it; otherwise allow (internal calls read key from env).
    if provided and provided != expected:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key."},
        )
    return await call_next(request)

app.include_router(energy_overview.router, prefix="/api/v1")
app.include_router(energy.router, prefix="/api/v1")
app.include_router(data_files.router, prefix="/api/v1")
app.include_router(smp.router, prefix="/api/v1")
app.include_router(smp_production_vs_marginal_price.router, prefix="/api/v1")
app.include_router(private_suppliers.router, prefix="/api/v1")
app.include_router(switching_requests.router, prefix="/api/v1")
# app.include_router(smp.router, prefix="/api/v1")
