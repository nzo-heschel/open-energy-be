# app/api/v1/co2_emissions_mix.py
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query

from app.services.co2_emission_savings_service_ import NogaCO2Service
from app.services.co2_emission_savings_processor import CO2Processor
from app.utils.date_utils import resolve_date_range, to_noga_date

load_dotenv()

router = APIRouter(prefix="/co2", tags=["CO2"])


class ViewFilter(str, Enum):
    DAY = "day"      # hourly breakdown
    MONTH = "month"  # daily breakdown (default)
    YEAR = "year"    # monthly breakdown


@router.get("/emissions-mix")
async def get_emissions_mix(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: ViewFilter = Query(default=ViewFilter.MONTH, description="Filter: day, month, year"),
) -> Dict:
    """
    Endpoint 4 - CO2 Emissions Mix (Pie Chart + Infographics)
    
    Title on site: תמהיל פליטות CO2 -> "CO2 Emissions Mix"

    Features:
    - Pie chart breakdown by fuel: coal, natural gas, diesel (excludes mazut, methanol)
    - Filters: day, month, year, between dates (default: month)
    - Infographics: Total emissions excluding renewables, Emissions avoided through renewables
    - Emissions per kWh calculation
    - Time series data for detailed charts

    Calculation: Sum samples in selected period and divide by 12
    """
    try:
        # Set default days based on view
        if view == ViewFilter.DAY:
            default_days = 1
        elif view == ViewFilter.MONTH:
            default_days = 30
        else:  # YEAR
            default_days = 365

        start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=default_days)

        subscription_key = os.getenv("CO2_TOKEN")

        raw = await NogaCO2Service.fetch_co2_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            subscription_key,
        )

        if not raw:
            raise ValueError("No CO2 samples returned for the selected period.")

        
        # AGGREGATE TOTALS FOR PIE CHART
        
        total_coal = 0.0
        total_gas = 0.0
        total_diesel = 0.0
        total_demand = 0.0  # For emissions per kWh calculation
        total_ratio_sum = 0.0  # Sum of co2_ratio values for calculating emissions avoided

        for sample in raw:
            coal = CO2Processor._as_float(sample.get("co2_coal", 0)) or 0
            gas = CO2Processor._as_float(sample.get("co2_gas", 0)) or 0
            diesel = CO2Processor._as_float(sample.get("co2_diesel", 0)) or 0
            demand = CO2Processor._as_float(sample.get("co2_current_demand", 0)) or 0
            ratio = CO2Processor._as_float(sample.get("co2_ratio", 0)) or 0
            
            total_coal += coal
            total_gas += gas
            total_diesel += diesel
            total_demand += demand
            total_ratio_sum += ratio

        # Divide by 12 as per requirement (12 samples per hour)
        total_coal = total_coal / 12.0
        total_gas = total_gas / 12.0
        total_diesel = total_diesel / 12.0
        total_demand = total_demand / 12.0
        total_ratio_sum = total_ratio_sum / 12.0

        # Total emissions (excluding mazut and methanol as per requirement)
        total_emissions = total_coal + total_gas + total_diesel

        # Emissions per kWh (convert MWh to kWh: multiply demand by 1000)
        total_kwh = total_demand * 1000  # MWh to kWh
        emissions_per_kwh = (total_emissions / total_kwh) if total_kwh > 0 else 0

        
        # PIE CHART DATA
        
        pie_chart = {
            "coal": {
                "value": round(total_coal, 2),
                "percentage": round((total_coal / total_emissions * 100) if total_emissions > 0 else 0, 2),
                "unit": "tons CO2",
            },
            "natural_gas": {
                "value": round(total_gas, 2),
                "percentage": round((total_gas / total_emissions * 100) if total_emissions > 0 else 0, 2),
                "unit": "tons CO2",
            },
            "diesel": {
                "value": round(total_diesel, 2),
                "percentage": round((total_diesel / total_emissions * 100) if total_emissions > 0 else 0, 2),
                "unit": "tons CO2",
            },
        }

        
        # TIME SERIES DATA FOR DETAILED CHARTS
        
        time_series = _build_time_series(raw, view, start_dt, end_dt)

        
        # INFOGRAPHICS DATA
        # Calculate avoided emissions using a baseline intensity (approx 0.55 tons/MWh for fossil grid)
        # Avoided = (Total Demand * Baseline) - Actual Emissions
        baseline_intensity = 0.55
        emissions_avoided = (total_demand * baseline_intensity) - total_emissions
        if emissions_avoided < 0:
            emissions_avoided = 0.0

        infographics = {
            "total_emissions_excluding_renewables": {
                "value": round(total_emissions, 2),
                "unit": "tons CO2",
                "description": "Total CO2 emissions from fossil fuels (coal + gas + diesel)"
            },
            "emissions_avoided_through_renewables": {
                "value": round(emissions_avoided, 2),
                "unit": "tons CO2",
                "description": "Estimated CO2 emissions avoided due to renewable energy generation (assuming 0.55t/MWh baseline)"
            },
        }

        
        # RESPONSE
        
        return {
            "view": view.value,
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
            "total_emissions": round(total_emissions, 2),
            "total_emissions_unit": "tons CO2",
            "emissions_per_kwh": round(emissions_per_kwh, 6),
            "emissions_per_kwh_unit": "tons CO2/kWh",
            "total_generation_mwh": round(total_demand, 2),
            "pie_chart": pie_chart,
            "infographics": infographics,
            "time_series": time_series,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to compute CO2 emissions mix: {str(e)}")


def _build_time_series(raw: List[Dict], view: ViewFilter, start_dt: datetime, end_dt: datetime) -> List[Dict]:
    """
    Build time series data bucketed according to the view filter.
    - day: hourly points
    - month: daily points (default)
    - year: monthly points
    """
    buckets: Dict[str, Dict] = {}

    for sample in raw:
        date_str = sample.get("date", "")
        time_str = sample.get("time", "00:00:00")
        
        try:
            # Parse the timestamp
            if time_str:
                ts = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")
            else:
                ts = datetime.strptime(date_str, "%d-%m-%Y")
        except (ValueError, TypeError):
            continue

        # Determine bucket key based on view
        if view == ViewFilter.DAY:
            bucket_key = ts.strftime("%Y-%m-%d %H:00")
            label = ts.strftime("%H:%M")
        elif view == ViewFilter.MONTH:
            bucket_key = ts.strftime("%Y-%m-%d")
            label = ts.strftime("%d %b")
        else:  # YEAR
            bucket_key = ts.strftime("%Y-%m")
            label = ts.strftime("%b %Y")

        if bucket_key not in buckets:
            buckets[bucket_key] = {
                "period": bucket_key,
                "label": label,
                "coal": 0.0,
                "natural_gas": 0.0,
                "diesel": 0.0,
                "total": 0.0,
                "demand": 0.0,
                "sample_count": 0,
            }

        coal = CO2Processor._as_float(sample.get("co2_coal", 0)) or 0
        gas = CO2Processor._as_float(sample.get("co2_gas", 0)) or 0
        diesel = CO2Processor._as_float(sample.get("co2_diesel", 0)) or 0
        demand = CO2Processor._as_float(sample.get("co2_current_demand", 0)) or 0

        buckets[bucket_key]["coal"] += coal
        buckets[bucket_key]["natural_gas"] += gas
        buckets[bucket_key]["diesel"] += diesel
        buckets[bucket_key]["total"] += coal + gas + diesel
        buckets[bucket_key]["demand"] += demand
        buckets[bucket_key]["sample_count"] += 1

    # Convert to list and apply /12 calculation
    series = []
    for bucket_key in sorted(buckets.keys()):
        bucket = buckets[bucket_key]
        # Divide by 12 as per requirement
        coal = bucket["coal"] / 12.0
        gas = bucket["natural_gas"] / 12.0
        diesel = bucket["diesel"] / 12.0
        total = bucket["total"] / 12.0
        demand = bucket["demand"] / 12.0
        
        # Emissions per kWh for this period
        kwh = demand * 1000
        emissions_per_kwh = (total / kwh) if kwh > 0 else 0

        series.append({
            "period": bucket["period"],
            "label": bucket["label"],
            "coal": round(coal, 2),
            "natural_gas": round(gas, 2),
            "diesel": round(diesel, 2),
            "total_emissions": round(total, 2),
            "generation_mwh": round(demand, 2),
            "emissions_per_kwh": round(emissions_per_kwh, 6),
            "unit": "tons CO2",
        })

    return series
