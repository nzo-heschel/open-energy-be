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
from fastapi.middleware.cors import CORSMiddleware
# Delivery 3
from app.api.v1 import co2_emission_savings
from app.api.v1 import co2_emissions_ratio
from app.api.v1 import co2_total_production
from app.api.v1 import co2_emissions_mix
from app.api.v1 import co2_emissions_over_time
from app.api.v1 import co2_total_vs_ratio
from app.api.v1 import heat_load_vs_generation
# Delivery 2 – Installed Capacity & Response Capacity
from app.api.v1 import installed_capacity
from app.api.v1 import response_capacity
# Delivery 4 – Forecasts & comparisons
from app.api.v1 import delivery4_forecasts


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
    if request.method == "OPTIONS":
        return await call_next(request)
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
    provided = request.headers.get("X-Api-Key")
    
    if not provided or provided != expected:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key."},
        )
    return await call_next(request)


allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
origins = [
    "https://open-energy-fe.vercel.app",
    "http://localhost:3000",
    "https://open-energy-be-vo4yi.ondigitalocean.app",
    "https://localhost:8000",
]
if allowed_origins_env:
    if allowed_origins_env.strip() == "*":
        origins = ["*"]
    else:
        for origin in allowed_origins_env.split(","):
            cleaned = origin.strip()
            if cleaned and cleaned not in origins:
                origins.append(cleaned)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Delivery 1
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
# Delivery 3 - CO2 endpoints
app.include_router(co2_emission_savings.router, prefix="/api/v1")
app.include_router(co2_emissions_ratio.router, prefix="/api/v1")
app.include_router(co2_total_production.router, prefix="/api/v1")
app.include_router(co2_emissions_mix.router, prefix="/api/v1")
app.include_router(co2_emissions_over_time.router, prefix="/api/v1")
app.include_router(co2_total_vs_ratio.router, prefix="/api/v1")
app.include_router(heat_load_vs_generation.router, prefix="/api/v1")
# Delivery 2 – Connected Facilities & Distributor Responses
app.include_router(installed_capacity.router, prefix="/api/v1")
app.include_router(response_capacity.router, prefix="/api/v1")
# Delivery 4 – Diagram 1 + Diagram 2. Public URLs use the clean renewables path;
# development-era and legacy prefixes stay available as hidden compatibility aliases.
app.include_router(
    delivery4_forecasts.router,
    prefix="/api/v1/renewables",
)
app.include_router(
    delivery4_forecasts.router,
    prefix="/api/v1/renewables/delivery-4",
    include_in_schema=False,
)
app.include_router(
    delivery4_forecasts.router,
    prefix="/api/v1/forecasts",
    include_in_schema=False,
)



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
