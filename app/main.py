# app/main.py
from fastapi import FastAPI
from app.api.v1 import energy

app = FastAPI(title="Electricity Production Mix API")

app.include_router(energy.router)
