# app/api/v1/co2_emissions_mix.py
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import pandas as pd

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
        
        totals = CO2Processor.aggregate_totals(raw)
        components = totals["components"]
        total_coal = components["coal"]
        total_gas = components["natural_gas"]
        total_diesel = components["diesel"]
        total_emissions = totals["total_emissions"]
        total_demand = totals["generation_mwh"]
        emissions_per_kwh = totals["emissions_per_kwh"]

        
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

        
        infographics = {
            "total_emissions_excluding_renewables": {
                # Fossil emission RATE (שיעור פליטות CO2 ממקורות פוסיליים):
                # average mTCO2/h over the period, per client spec — not the
                # period total. The total is still available at top-level
                # `total_emissions` for any caller that needs it.
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
            **CO2Processor.hierarchy_from_totals(totals),
            "time_series": time_series,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to compute CO2 emissions mix: {str(e)}")


@router.get("/emissions-mix/export")
async def export_emissions_mix(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: ViewFilter = Query(default=ViewFilter.MONTH, description="Filter: day, month, year"),
):
    payload = await get_emissions_mix(start_date=start_date, end_date=end_date, view=view)
    contents = _to_excel_bytes(payload)
    filename = f"co2_emissions_mix_{payload['start_date']}_to_{payload['end_date']}.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
        fuel_oil = CO2Processor._as_float(sample.get("co2_fuel_oil", 0)) or 0
        methanol = CO2Processor._as_float(sample.get("co2_methanol", 0)) or 0
        demand = CO2Processor._as_float(sample.get("co2_current_demand", 0)) or 0
        savings = CO2Processor._as_float(sample.get("co2_renewables", 0)) or 0

        buckets[bucket_key]["coal"] += coal
        buckets[bucket_key]["natural_gas"] += gas
        buckets[bucket_key]["diesel"] += diesel
        buckets[bucket_key]["fuel_oil"] = buckets[bucket_key].get("fuel_oil", 0.0) + fuel_oil
        buckets[bucket_key]["methanol"] = buckets[bucket_key].get("methanol", 0.0) + methanol
        buckets[bucket_key]["total"] += coal + gas + diesel + fuel_oil + methanol
        buckets[bucket_key]["demand"] += demand
        buckets[bucket_key]["savings"] = buckets[bucket_key].get("savings", 0.0) + savings
        buckets[bucket_key]["sample_count"] += 1

    # Convert to list and apply /12 calculation
    series = []
    for bucket_key in sorted(buckets.keys()):
        bucket = buckets[bucket_key]
        # Divide by 12 as per requirement
        coal = bucket["coal"] / 12.0
        gas = bucket["natural_gas"] / 12.0
        diesel = bucket["diesel"] / 12.0
        fuel_oil = bucket.get("fuel_oil", 0.0) / 12.0
        methanol = bucket.get("methanol", 0.0) / 12.0
        total = bucket["total"] / 12.0
        demand = bucket["demand"] / 12.0
        savings = bucket.get("savings", 0.0) / 12.0
        
        # Emissions per kWh for this period
        kwh = demand * 1000
        emissions_per_kwh = (total / kwh) if kwh > 0 else 0

        series.append({
            "period": bucket["period"],
            "label": bucket["label"],
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
            "unit": "tons CO2",
        })

    return series


def _to_excel_bytes(payload: Dict) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_rows = [
            {"metric": "view", "value": payload.get("view")},
            {"metric": "start_date", "value": payload.get("start_date")},
            {"metric": "end_date", "value": payload.get("end_date")},
            {"metric": "total_emissions", "value": payload.get("total_emissions")},
            {"metric": "total_emissions_unit", "value": payload.get("total_emissions_unit")},
            {"metric": "emissions_per_kwh", "value": payload.get("emissions_per_kwh")},
            {"metric": "emissions_per_kwh_unit", "value": payload.get("emissions_per_kwh_unit")},
            {"metric": "total_generation_mwh", "value": payload.get("total_generation_mwh")},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        pie = payload.get("pie_chart") or {}
        if isinstance(pie, dict) and pie:
            pie_rows = []
            for fuel, data in pie.items():
                row = {
                    "fuel": fuel,
                    "value": (data or {}).get("value"),
                    "percentage": (data or {}).get("percentage"),
                    "unit": (data or {}).get("unit"),
                }
                pie_rows.append(row)
            pd.DataFrame(pie_rows).to_excel(writer, sheet_name="Pie", index=False)

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

        series = payload.get("time_series") or []
        if series:
            pd.DataFrame(series).to_excel(writer, sheet_name="TimeSeries", index=False)

    buffer.seek(0)
    return buffer.getvalue()
