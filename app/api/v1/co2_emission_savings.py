# app/api/v1/co2_emission_savings.py
import os
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from app.services.co2_emission_savings_service_ import NogaCO2Service
from app.services.co2_emission_savings_processor import CO2Processor
from app.utils.date_utils import resolve_date_range, to_noga_date

load_dotenv()

router = APIRouter(prefix="/co2", tags=["CO2"])


@router.get("/emissions-savings")
async def get_emissions_savings(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict:
    """
    CO2 Emissions Savings — total view.

    Title on site: חיסכון בפליטות CO2 → "CO2 Emissions Savings"

    The savings figure is the CO2 emissions avoided because demand was met
    by renewables instead of fossil fuels. NZO publishes this directly in
    its `Renewables` CO2 field (mapped to `co2_renewables` internally).
    Every 5-min sample is an instantaneous tons CO2/h rate, so summing the
    rates and dividing by 12 yields total tons CO2 for the period.
    """
    try:
        start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=30)

        subscription_key = os.getenv("CO2_TOKEN")

        raw = await NogaCO2Service.fetch_co2_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            subscription_key,
        )

        if not raw:
            raise ValueError("No CO2 samples returned for the selected period.")

        savings = CO2Processor.sum_samples_divide_by_12(raw, "co2_renewables")

        return {
            "total": round(savings, 2),
            "unit": "tons CO2",
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to compute emissions savings: {str(e)}")
