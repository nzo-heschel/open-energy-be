# app/api/v1/co2_emissions_ratio.py
import os
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from app.services.co2_emission_savings_service_ import NogaCO2Service
from app.services.co2_emission_savings_processor import CO2Processor
from app.utils.date_utils import resolve_date_range, to_noga_date

load_dotenv()

router = APIRouter(prefix="/co2", tags=["CO2"])


@router.get("/emissions-ratio")
async def get_emissions_ratio(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict:
    """
    CO2 Emissions Ratio (intensity) — total view.

    Title on site: יחס פליטות CO2 / עצימות פליטות CO2 → "CO2 Emissions Intensity"

    Defined as the energy-weighted average emission factor for the period:

        intensity = total_fossil_emissions (tons CO2) / total_demand (MWh)

    This is the standard grid-emissions-intensity metric. It is *not* the
    arithmetic mean of NZO's per-sample `Co2Ratio`, which would over-weight
    low-load periods.
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

        totals = CO2Processor.aggregate_totals(raw)

        return {
            "total": round(totals["emissions_ratio"], 4),
            "unit": "tons CO2/MWh",
            "total_emissions": round(totals["total_emissions"], 2),
            "total_emissions_unit": "tons CO2",
            "total_generation_mwh": round(totals["generation_mwh"], 2),
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to compute CO2 emissions ratio: {str(e)}")
