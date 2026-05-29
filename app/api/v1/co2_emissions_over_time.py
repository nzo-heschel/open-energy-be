# app/api/v1/co2_emissions_over_time.py
import os
from typing import Dict, List, Optional
from datetime import datetime
from io import BytesIO

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from enum import Enum
import pandas as pd

from app.services.co2_emission_savings_service_ import NogaCO2Service
from app.services.co2_emission_savings_processor import CO2Processor
from app.utils.date_utils import resolve_date_range, to_noga_date

load_dotenv()

router = APIRouter(prefix="/co2", tags=["CO2"])


class ViewFilter(str, Enum):
    MONTH = "month"  # daily granularity (default)
    YEAR = "year"    # monthly granularity
    CUSTOM = "custom"


@router.get("/emissions-over-time")
async def get_emissions_over_time(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: ViewFilter = Query(default=ViewFilter.MONTH, description="Filter: month, year, or custom range"),
) -> Dict:
    """
    Endpoint 5 - CO2 Emissions Over Time
    
    Title on site: פליטות CO2 על פני זמן -> "CO2 Emissions Over Time"

    Features:
    - Time-series chart (daily/monthly points)
    - Breakdown by fuel: coal, natural gas, diesel (excludes mazut, methanol)
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
                # Fossil emission RATE (mTCO2/h), per client spec — see note
                # in co2_emissions_mix. Period total stays at top-level
                # `total_emissions`.
                "value": round(totals.get("fossil_emissions_rate", 0.0), 2),
                "unit": "mTCO2/h",
                "description": "Average CO2 emission rate from fossil fuels (coal + gas + diesel + fuel oil + methanol), in metric tons CO2 per hour"
            },
            "emissions_avoided_through_renewables": {
                "value": round(totals["renewable_savings"], 2),
                "unit": "tons CO2",
                "percentage_of_actual_plus_savings": round(totals["renewable_savings_percent"], 2),
                "description": "CO2 emissions savings from renewable generation, using the source Renewables field"
            },
        }

        
        # TIME SERIES DATA
        
        # Identify granularity based on view
        # If view is year -> monthly points
        # If view is month -> daily points
        # If view is custom -> depends on range, but usually daily if < 2 months, else monthly? 
        # The prompt says "Default: month. Filter by: month (daily granularity)".
        # Let's stick to: Year=Monthly, everything else=Daily.
        
        granularity = "daily"
        if view == ViewFilter.YEAR:
            granularity = "monthly"
        
        time_series = _build_time_series(raw, granularity)

        return {
            "view": view.value,
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
            "infographics": infographics,
            **CO2Processor.hierarchy_from_totals(totals),
            "chart_data": time_series
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to compute CO2 emissions over time: {str(e)}")


@router.get("/emissions-over-time/export")
async def export_emissions_over_time(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: ViewFilter = Query(default=ViewFilter.MONTH, description="Filter: month, year, or custom range"),
) -> Dict:
    payload = await get_emissions_over_time(start_date=start_date, end_date=end_date, view=view)
    contents = _to_excel_bytes(payload)
    filename = f"co2_emissions_over_time_{payload['start_date']}_to_{payload['end_date']}.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _build_time_series(raw: List[Dict], granularity: str) -> List[Dict]:
    buckets: Dict[str, Dict] = {}

    for sample in raw:
        date_str = sample.get("date", "")
        # Time string often exists, but we mainly care about date for daily/monthly aggregation
        
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
                "total": 0.0,
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
        buckets[bucket_key]["total"] += (coal + gas + diesel + fuel_oil + methanol)
        buckets[bucket_key]["demand"] += demand
        buckets[bucket_key]["savings"] += savings

    # Finalize buckets
    series = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        
        # Divide by 12 aggregation rule
        coal = b["coal"] / 12.0
        gas = b["natural_gas"] / 12.0
        diesel = b["diesel"] / 12.0
        fuel_oil = b["fuel_oil"] / 12.0
        methanol = b["methanol"] / 12.0
        total = b["total"] / 12.0
        demand = b["demand"] / 12.0
        savings = b["savings"] / 12.0
        
        # Emissions per kWh
        # 1 MWh = 1000 kWh
        kwh = demand * 1000.0
        emissions_per_kwh = (total / kwh) if kwh > 0 else 0

        series.append({
            "period": b["period"],
            "label": b["label"],
            "coal": round(coal, 2),
            "natural_gas": round(gas, 2),
            "diesel": round(diesel, 2),
            "fuel_oil": round(fuel_oil, 2),
            "methanol": round(methanol, 2),
            "total_emissions": round(total, 2),
            "emissions_savings": round(savings, 2),
            "generation_mwh": round(demand, 2),
            "emissions_ratio": round(total / demand, 4) if demand > 0 else 0,
            "emissions_per_kwh": round(emissions_per_kwh, 6),
            "level1": {
                "fossil_emissions": round(total, 2),
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
            "unit": "tons CO2"
        })
    
    return series


def _to_excel_bytes(payload: Dict) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_rows = [
            {"metric": "view", "value": payload.get("view")},
            {"metric": "start_date", "value": payload.get("start_date")},
            {"metric": "end_date", "value": payload.get("end_date")},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        infographics = payload.get("infographics") or {}
        if isinstance(infographics, dict) and infographics:
            info_rows = []
            for key, data in infographics.items():
                row = {
                    "metric": key,
                    "value": (data or {}).get("value"),
                    "unit": (data or {}).get("unit"),
                    "description": (data or {}).get("description"),
                }
                info_rows.append(row)
            pd.DataFrame(info_rows).to_excel(writer, sheet_name="Infographics", index=False)

        chart_data = payload.get("chart_data") or []
        if chart_data:
            pd.DataFrame(chart_data).to_excel(writer, sheet_name="ChartData", index=False)

    buffer.seek(0)
    return buffer.getvalue()
