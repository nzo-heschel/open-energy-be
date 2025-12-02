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
NOGA_TOKEN = os.getenv("NOGA_API_TOKEN", "7b397cafa75b4a00848542829a588dac")

@router.get("/")
async def get_smp_data(start_date: str = None, end_date: str = None) -> Dict:
    try:
        start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=30)
        raw_smp_data = await SMPService.fetch_smp_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            NOGA_TOKEN,
        )
        smp_data = SMPProcessor.process_smp_data(raw_smp_data)
        return smp_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch SMP data: {str(e)}")
