# app/api/v1/smp.py
import os
from fastapi import APIRouter, HTTPException
from typing import Dict
from app.services.smp_service import SMPService
from app.services.smp_processor import SMPProcessor
from app.utils.date_utils import resolve_date_range, to_noga_date
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/energy/smp", tags=["SMP"])
# Prefer SMP_TOKEN; fall back to NOGA_API_TOKEN; finally, use legacy default token for compatibility.
SMP_TOKEN = (
    os.getenv("SMP_TOKEN")
    or os.getenv("NOGA_API_TOKEN")
)

@router.get("/")
async def get_smp_data(start_date: str = None, end_date: str = None) -> Dict:
    try:
        start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=1)
        raw_smp_data = await SMPService.fetch_smp_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            SMP_TOKEN,
        )
        days_delta = (end_dt - start_dt).days
        if days_delta <= 1:
            view = "day"
        elif days_delta <= 45:
            view = "month"
        else:
            view = "year"

        include_samples = view == "day"
        smp_data = SMPProcessor.process_smp_data(raw_smp_data, include_samples=include_samples)
        has_prices = smp_data.get("chart_with_constraints") or smp_data.get("chart_without_constraints")
        if not has_prices:
            raise HTTPException(
                status_code=424,
                detail=(
                    "SMP price fields were not returned by the NOGA API. "
                    "Verify that the SMP endpoint is accessible with the provided subscription key."
                ),
            )

        days_delta = (end_dt - start_dt).days
        smp_data["view"] = view
        smp_data["start_date"] = start_dt.date().isoformat()
        smp_data["end_date"] = end_dt.date().isoformat()
        return smp_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to fetch SMP data: {str(e)}")
