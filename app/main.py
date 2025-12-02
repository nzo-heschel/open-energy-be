# app/main.py
from fastapi import FastAPI
from app.api.v1 import energy
from app.api.v1 import energy_overview
from app.api.v1 import smp
from app.api.v1 import smp_production_vs_marginal_price



app = FastAPI(title="Electricity Production Mix API")

app.include_router(energy_overview.router, prefix="/api/v1")
app.include_router(energy.router, prefix="/api/v1")
app.include_router(smp.router, prefix="/api/v1")
app.include_router(smp_production_vs_marginal_price.router, prefix="/api/v1")
# app.include_router(smp.router, prefix="/api/v1")
