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
        
        totals = CO2Processor.aggregate_totals(raw)

        infographics = {
            "total_emissions_excluding_renewables": {
                "value": round(totals["total_emissions"], 2),
                "unit": "tons CO2",
                "description": "Total CO2 emissions from fossil fuels (coal + gas + diesel + fuel oil + methanol)"
            },
            "emissions_avoided_through_renewables": {
                "value": round(totals["renewable_savings"], 2),
                "unit": "tons CO2",
                "percentage_of_actual_plus_savings": round(totals["renewable_savings_percent"], 2),
                "description": "CO2 emissions savings from renewable generation, using the source Renewables field"
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
            **CO2Processor.hierarchy_from_totals(totals),
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
        "fuel_oil",
        "methanol",
        "emissions_savings",
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
                "fuel_oil": 0.0,
                "methanol": 0.0,
                "total_emissions": 0.0,
                "demand": 0.0,
                "savings": 0.0,
            }

        coal = CO2Processor._as_float(sample.get("co2_coal", 0)) or 0
        gas = CO2Processor._as_float(sample.get("co2_gas", 0)) or 0
        diesel = CO2Processor._as_float(sample.get("co2_diesel", 0)) or 0
        fuel_oil = CO2Processor._as_float(sample.get("co2_fuel_oil", 0)) or 0
        methanol = CO2Processor._as_float(sample.get("co2_methanol", 0)) or 0
        demand = CO2Processor._as_float(sample.get("co2_current_demand", 0)) or 0
        savings = CO2Processor._as_float(sample.get("co2_renewables", 0)) or 0

        buckets[bucket_key]["coal"] += coal
        buckets[bucket_key]["natural_gas"] += gas
        buckets[bucket_key]["diesel"] += diesel
        buckets[bucket_key]["fuel_oil"] += fuel_oil
        buckets[bucket_key]["methanol"] += methanol
        buckets[bucket_key]["total_emissions"] += (coal + gas + diesel + fuel_oil + methanol)
        buckets[bucket_key]["demand"] += demand
        buckets[bucket_key]["savings"] += savings

    # Finalize buckets
    series = []
    for key in sorted(buckets.keys()):
        b = buckets[key]

        # Divide by 12 aggregation rule for ALL summed values
        coal = b["coal"] / 12.0
        gas = b["natural_gas"] / 12.0
        diesel = b["diesel"] / 12.0
        fuel_oil = b["fuel_oil"] / 12.0
        methanol = b["methanol"] / 12.0
        total_emissions = b["total_emissions"] / 12.0
        demand = b["demand"] / 12.0
        savings = b["savings"] / 12.0
        # Ratio: divide raw 5-min sums, then apply /12 as the last step (client spec).
        emissions_ratio = (
            (b["total_emissions"] / b["demand"]) / 12.0 if b["demand"] > 0 else 0.0
        )

        # Emissions per kWh
        kwh = demand * 1000.0
        emissions_per_kwh = (total_emissions / kwh) if kwh > 0 else 0

        series.append({
            "period": b["period"],
            "label": b["label"],
            "total_emissions": round(total_emissions, 2),
            "emissions_ratio": round(emissions_ratio, 4), # Weighted fossil emissions / generation MWh
            "coal": round(coal, 2),
            "natural_gas": round(gas, 2),
            "diesel": round(diesel, 2),
            "fuel_oil": round(fuel_oil, 2),
            "methanol": round(methanol, 2),
            "emissions_savings": round(savings, 2),
            "generation_mwh": round(demand, 2),
            "emissions_per_kwh": round(emissions_per_kwh, 6),
            "level1": {
                "fossil_emissions": round(total_emissions, 2),
                "renewable_emissions_savings": round(savings, 2),
            },
            "level2": {
                "fossil_emissions": {
                    "coal": round(coal, 2),
                    "fuel_oil": round(fuel_oil, 2),
                    "natural_gas": round(gas, 2),
                    "diesel": round(diesel, 2),
                    "methanol": round(methanol, 2),
                },
                "renewable_emissions_savings": {
                    "renewables": round(savings, 2),
                },
            },
            "unit_emissions": "tons CO2",
            "unit_ratio": "tons CO2/MWh"
        })
    
    return series
