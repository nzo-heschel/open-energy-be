# app/api/v1/co2.py
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
    Endpoint 1 - Emissions Savings (Total view only)

    Steps (per Delivery-3):
    - Fetch CO2 emissions data from NOGA for selected period.
    - Compute total: sum all samples and divide by 12.
    - Return total only.
    
    The CO2 API returns fields: co2_coal, co2_gas, co2_diesel, co2_current_demand, co2_ratio
    Total emissions = co2_coal + co2_gas + co2_diesel
    """
    try:
        # Aligning with CO2 endpoints default (month-style): 30 days
        start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=30)

        subscription_key = os.getenv("CO2_TOKEN")

        raw = await NogaCO2Service.fetch_co2_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            subscription_key,
        )

        if not raw:
            raise ValueError("No CO2 samples returned for the selected period.")

        # Calculate total emissions (sum co2_coal + co2_gas + co2_diesel) / 12
        # Data is sampled every 5 minutes = 12 samples/hour
        total_emissions = 0.0
        for sample in raw:
            coal = CO2Processor._as_float(sample.get("co2_coal", 0)) or 0
            gas = CO2Processor._as_float(sample.get("co2_gas", 0)) or 0
            diesel = CO2Processor._as_float(sample.get("co2_diesel", 0)) or 0
            total_emissions += coal + gas + diesel
        
        # Divide by 12 as per requirement (12 samples per hour)
        total_emissions = total_emissions / 12.0

        # Requirement says: total value only ("Total view")
        return {
            "total": round(total_emissions, 2),
            "unit": "tons CO2",
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to compute emissions savings: {str(e)}")
