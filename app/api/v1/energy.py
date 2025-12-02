# app/api/v1/energy.py
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from io import StringIO
import csv
from typing import Dict
from app.services.noga_service import NogaService
from app.utils.date_utils import resolve_date_range, to_iso_date, to_noga_date
from app.utils.response_formatter import flatten_level2, format_categories

router = APIRouter(prefix="/energy", tags=["Energy"])
NOGA_TOKEN = os.getenv("NOGA_API_TOKEN", "7b397cafa75b4a00848542829a588dac")


# --------------------------
# HOURLY AVERAGING (5-min to hourly)
# --------------------------
def hourly_average(values):
    """
    values: list of {'date': 'dd-mm-yyyy', 'time': 'HH:MM:SS', ...}
    return: averaged list, one per hour
    """

    grouped = {}
    for v in values:
        hour_key = f"{v['date']} {v['time'][:2]}"  # YYYY-MM-DD HH
        grouped.setdefault(hour_key, []).append(v)

    hourly = []
    for hour, items in grouped.items():
        avg_entry = {"hour": hour}

        for key in items[0].keys():
            if key in ["date", "time"]:
                continue
            avg_entry[key] = sum(i.get(key, 0) for i in items) / 12  # average of 12 x 5 min

        hourly.append(avg_entry)

    return hourly


# --------------------------
# MAIN ENDPOINT
# --------------------------
@router.get("/production-mix")
async def get_production_mix(
    start_date: str = None,
    end_date: str = None
) -> Dict:
    """
    Returns Israel's electricity production mix (aggregated).
    """

    start_dt, end_dt = resolve_date_range(start_date, end_date)

    try:
        raw_values = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            NOGA_TOKEN,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Step 1: hourly averaging
    hourly_values = hourly_average(raw_values)

    # Step 2: category aggregation
    # Step 3: level 2 details
    level2 = {
        "Non-renewables": {
            "coal": sum(v.get("coal", 0) for v in hourly_values),
            "natural_Gas": sum(v.get("natural_Gas", 0) for v in hourly_values),
            "diesel": sum(v.get("mazut", 0) for v in hourly_values),
        },
        "Renewables": {
            "photoVoltaic": sum(v.get("photoVoltaic", 0) for v in hourly_values),
            "biogas": sum(v.get("bio_Gas", 0) for v in hourly_values),
            "wind": sum(v.get("wind", 0) for v in hourly_values),
            "solar_thermal": sum(v.get("termo_Soler", 0) for v in hourly_values),
            "pv_storage": sum(v.get("photovoltaicIntegrated", 0) for v in hourly_values),
        },
        "Other": {
            "other": sum(v.get("other", 0) for v in hourly_values),
            "pumped_storage": sum(v.get("pumpedStorage", 0) for v in hourly_values),
        }
    }

    categories = format_categories(flatten_level2(level2))

    return {
        "start_date": to_iso_date(start_dt),
        "end_date": to_iso_date(end_dt),
        "categories": categories,
        "tooltip": (
            "The pie chart shows Israel's electricity generation mix and illustrates "
            "the different energy sources. The data are updated hourly and are based "
            "on real-time figures from the NOGA system operator."
        ),
    }


# ----------------------------------------------------------
# EXPORT TO EXCEL (CSV)
# ----------------------------------------------------------
@router.get("/production-mix/export")
async def export_energy_mix(
    start_date: str = None,
    end_date: str = None
):

    start_dt, end_dt = resolve_date_range(start_date, end_date)

    raw_values = await NogaService.fetch_production_mix(
        to_noga_date(start_dt),
        to_noga_date(end_dt),
        NOGA_TOKEN,
    )
    hourly_values = hourly_average(raw_values)
    aggregated = NogaService.aggregate_energy(hourly_values)

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Category", "Value"])
    for k, v in aggregated.items():
        writer.writerow([k, v])

    output.seek(0)
    file_name = "production_mix.csv"

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )
