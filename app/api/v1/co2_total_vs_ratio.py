# app/api/v1/co2_total_vs_ratio.py
import os
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from io import StringIO
import csv

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.co2_emission_savings_service_ import NogaCO2Service
from app.services.co2_emission_savings_processor import CO2Processor
from app.utils.date_utils import resolve_date_range, to_noga_date

load_dotenv()

router = APIRouter(prefix="/co2", tags=["CO2"])


class ViewFilter(str, Enum):
    MONTH = "month"  # daily granularity (default)
    YEAR = "year"    # monthly granularity
    CUSTOM = "custom"


@router.get("/total-vs-ratio")
async def get_total_vs_ratio(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: ViewFilter = Query(default=ViewFilter.MONTH, description="Filter: month, year, or custom range"),
) -> Dict:
    """
    Endpoint 6 - Total CO2 Emissions vs CO2 Emissions Ratio
    
    Title on site: כל פליטות CO2 מול יחס פליטות CO2 -> "Total CO2 Emissions vs CO2 Emissions Ratio"

    Features:
    - Combined chart comparing Total Emissions and Emissions Ratio over time
    - Breakdown by fuel for hover details: coal, natural gas, diesel
    - Infographics: Total emissions excluding renewables, Emissions avoided through renewables
    - Emissions per kWh calculation
    
    Calculation: Sum samples in selected period slice and divide by 12.
    """
    try:
        # Set default days based on view
        if view == ViewFilter.YEAR:
            default_days = 365
        else:
            default_days = 30 # Default for month and custom

        start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=default_days)

        subscription_key = os.getenv("CO2_TOKEN")

        raw = await NogaCO2Service.fetch_co2_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            subscription_key,
        )

        if not raw:
            raise ValueError("No CO2 samples returned for the selected period.")

        
        # AGGREGATE TOTALS FOR INFOGRAPHICS
        
        total_emissions = 0.0
        total_demand = 0.0

        for sample in raw:
            coal = CO2Processor._as_float(sample.get("co2_coal", 0)) or 0
            gas = CO2Processor._as_float(sample.get("co2_gas", 0)) or 0
            diesel = CO2Processor._as_float(sample.get("co2_diesel", 0)) or 0
            demand = CO2Processor._as_float(sample.get("co2_current_demand", 0)) or 0
            
            total_emissions += (coal + gas + diesel)
            total_demand += demand

        # Divide by 12 rules
        total_emissions /= 12.0
        total_demand /= 12.0

        # Calculate avoided emissions using a baseline intensity (approx 0.55 tons/MWh)
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
                "description": "Estimated CO2 emissions avoided due to renewable energy generation"
            },
        }

        
        # TIME SERIES DATA (Combined View)
        
        granularity = "daily"
        if view == ViewFilter.YEAR:
            granularity = "monthly"
        
        chart_data = _build_combined_time_series(raw, granularity)

        return {
            "view": view.value,
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
            "infographics": infographics,
            "chart_data": chart_data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to compute Total vs Ratio: {str(e)}")


@router.get("/total-vs-ratio/export-csv")
async def export_total_vs_ratio_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: ViewFilter = Query(default=ViewFilter.MONTH, description="Filter: month, year, or custom range"),
):
    """
    Export Total vs Ratio payload to CSV.
    """
    payload = await get_total_vs_ratio(start_date=start_date, end_date=end_date, view=view)
    chart_data = payload.get("chart_data", [])

    output = StringIO()
    fieldnames = [
        "period",
        "label",
        "total_emissions",
        "emissions_ratio",
        "coal",
        "natural_gas",
        "diesel",
        "generation_mwh",
        "emissions_per_kwh",
        "unit_emissions",
        "unit_ratio",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in chart_data:
        writer.writerow({k: row.get(k) for k in fieldnames})

    filename = f"co2_total_vs_ratio_{payload['start_date']}_to_{payload['end_date']}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _build_combined_time_series(raw: List[Dict], granularity: str) -> List[Dict]:
    buckets: Dict[str, Dict] = {}

    for sample in raw:
        date_str = sample.get("date", "")
        
        try:
             ts = datetime.strptime(date_str, "%d-%m-%Y")
        except (ValueError, TypeError):
            continue

        if granularity == "monthly":
            bucket_key = ts.strftime("%Y-%m")
            label = ts.strftime("%b %Y")
        else: # daily
            bucket_key = ts.strftime("%Y-%m-%d")
            label = ts.strftime("%d %b")

        if bucket_key not in buckets:
            buckets[bucket_key] = {
                "period": bucket_key,
                "label": label,
                "coal": 0.0,
                "natural_gas": 0.0,
                "diesel": 0.0,
                "total_emissions": 0.0,
                "total_ratio": 0.0, # Sum of ratios, will divide by 12 later
                "demand": 0.0
            }

        coal = CO2Processor._as_float(sample.get("co2_coal", 0)) or 0
        gas = CO2Processor._as_float(sample.get("co2_gas", 0)) or 0
        diesel = CO2Processor._as_float(sample.get("co2_diesel", 0)) or 0
        ratio = CO2Processor._as_float(sample.get("co2_ratio", 0)) or 0
        demand = CO2Processor._as_float(sample.get("co2_current_demand", 0)) or 0

        buckets[bucket_key]["coal"] += coal
        buckets[bucket_key]["natural_gas"] += gas
        buckets[bucket_key]["diesel"] += diesel
        buckets[bucket_key]["total_emissions"] += (coal + gas + diesel)
        buckets[bucket_key]["total_ratio"] += ratio
        buckets[bucket_key]["demand"] += demand

    # Finalize buckets
    series = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        
        # Divide by 12 aggregation rule for ALL summed values
        coal = b["coal"] / 12.0
        gas = b["natural_gas"] / 12.0
        diesel = b["diesel"] / 12.0
        total_emissions = b["total_emissions"] / 12.0
        total_ratio = b["total_ratio"] / 12.0 # Averaged/Aggregated ratio over the period
        demand = b["demand"] / 12.0
        
        # Emissions per kWh
        kwh = demand * 1000.0
        emissions_per_kwh = (total_emissions / kwh) if kwh > 0 else 0

        series.append({
            "period": b["period"],
            "label": b["label"],
            "total_emissions": round(total_emissions, 2),
            "emissions_ratio": round(total_ratio, 4), # PRIMARY METRIC 2
            "coal": round(coal, 2),
            "natural_gas": round(gas, 2),
            "diesel": round(diesel, 2),
            "generation_mwh": round(demand, 2),
            "emissions_per_kwh": round(emissions_per_kwh, 6),
            "unit_emissions": "tons CO2",
            "unit_ratio": "tons CO2/MWh"
        })
    
    return series
