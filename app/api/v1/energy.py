from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta
from io import StringIO
import csv
from typing import Dict
from app.services.noga_service import NogaService

router = APIRouter(prefix="/energy", tags=["Energy"])

# --------------------------
# Time filter logic
# --------------------------
def resolve_dates(filter: str):
    today = datetime.today()

    if filter == "day":
        start = end = today.strftime("%d-%m-%Y")

    elif filter == "month":
        start = today.replace(day=1).strftime("%d-%m-%Y")
        end = today.strftime("%d-%m-%Y")

    elif filter == "year":
        start = today.replace(month=1, day=1).strftime("%d-%m-%Y")
        end = today.strftime("%d-%m-%Y")

    elif filter == "decade":
        start = today.replace(year=today.year - 10).strftime("%d-%m-%Y")
        end = today.strftime("%d-%m-%Y")

    elif filter == "between":
        raise HTTPException(status_code=400, detail="Use /energy/production-mix/range")

    else:
        # default → last year
        start = today.replace(year=today.year - 1).strftime("%d-%m-%Y")
        end = today.strftime("%d-%m-%Y")

    return start, end


# --------------------------
# HOURLY AVERAGING (5-min → hourly)
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
            avg_entry[key] = sum(i.get(key, 0) for i in items) / 12  # average of 12 × 5 min

        hourly.append(avg_entry)

    return hourly


# --------------------------
# MAIN ENDPOINT
# --------------------------
@router.get("/production-mix")
async def get_production_mix(filter: str = Query("year")) -> Dict:
    """
    Returns Israel's electricity production mix (aggregated).
    """

    start, end = resolve_dates(filter)

    token = "7b397cafa75b4a00848542829a588dac"

    try:
        raw_values = await NogaService.fetch_production_mix(start, end, token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Step 1: hourly averaging
    hourly_values = hourly_average(raw_values)

    # Step 2: category aggregation
    aggregated = NogaService.aggregate_energy(hourly_values)

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

    return {
        "filter": filter,
        "start_date": start,
        "end_date": end,
        "level1": aggregated,
        "level2": level2,
        "tooltip": (
            "The pie chart shows Israel’s electricity generation mix and illustrates "
            "the different energy sources. The data are updated hourly and are based "
            "on real-time figures from the NOGA system operator."
        )
    }


# ----------------------------------------------------------
# EXPORT TO EXCEL (CSV)
# ----------------------------------------------------------
@router.get("/production-mix/export")
async def export_energy_mix(filter: str = Query("year")):

    start, end = resolve_dates(filter)
    token = "7b397cafa75b4a00848542829a588dac"

    raw_values = await NogaService.fetch_production_mix(start, end, token)
    hourly_values = hourly_average(raw_values)
    aggregated = NogaService.aggregate_energy(hourly_values)

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Category", "Value"])
    for k, v in aggregated.items():
        writer.writerow([k, v])

    output.seek(0)
    file_name = f"production_mix_{filter}.csv"

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )
