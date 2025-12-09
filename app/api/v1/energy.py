# app/api/v1/energy.py
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
import pandas as pd
from typing import Dict
from datetime import timedelta
from app.services.noga_service import NogaService
from app.utils.date_utils import resolve_date_range, to_iso_date, to_noga_date
from app.utils.response_formatter import flatten_level2, format_categories
from datetime import datetime

router = APIRouter(prefix="/energy", tags=["Energy"])
NOGA_TOKEN = os.getenv("NOGA_API_TOKEN", "7b397cafa75b4a00848542829a588dac")
# Keep default windows small to avoid slow/broken proxy downloads; override via env if needed.
DEFAULT_RANGE_DAYS = int(os.getenv("ENERGY_PRODUCTION_MIX_DEFAULT_DAYS", "30"))


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


def _aggregate_level2(hourly_values):
    """
    Aggregate hourly values into Delivery-1 Level-2 buckets.
    """
    level2 = {
        "non_renewables": {
            "coal": sum(v.get("coal", 0) for v in hourly_values),
            "natural_gas": sum(v.get("natural_Gas", 0) for v in hourly_values),
            "diesel": sum(v.get("mazut", 0) for v in hourly_values),
        },
        "renewables": {
            "photovoltaic": sum(v.get("photoVoltaic", 0) for v in hourly_values),
            "biogas": sum(v.get("bio_Gas", 0) for v in hourly_values),
            "wind": sum(v.get("wind", 0) for v in hourly_values),
            "solar_thermal": sum(v.get("termo_Soler", 0) for v in hourly_values),
            "pv_storage": sum(v.get("photovoltaicIntegrated", 0) for v in hourly_values),
        },
        "other": {
            "other": sum(v.get("other", 0) for v in hourly_values),
            "pumped_storage": sum(v.get("pumpedStorage", 0) for v in hourly_values),
        },
    }
    return level2


def _aggregate_level1(level2: Dict) -> Dict:
    return {
        "non_renewables": sum(level2["non_renewables"].values()),
        "renewables": sum(level2["renewables"].values()),
        "other": sum(level2["other"].values()),
    }


def _infer_filter(start_dt, end_dt):
    days = (end_dt - start_dt).days
    if days <= 1:
        return "day"
    if days <= 31:
        return "month"
    return "year"


def _filter_raw_values(values, start_dt, end_dt):
    """
    Keep only samples within the requested range.
    """
    filtered = []
    for v in values:
        try:
            ts = datetime.strptime(f"{v['date']} {v['time']}", "%d-%m-%Y %H:%M:%S")
        except Exception:
            try:
                ts = datetime.strptime(f"{v['date']} {v['time']}", "%d-%m-%Y %H:%M")
            except Exception:
                continue
        if start_dt <= ts <= end_dt + timedelta(seconds=59):
            filtered.append(v)
    return filtered


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

    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=DEFAULT_RANGE_DAYS)

    try:
        raw_values = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            NOGA_TOKEN,
        )
    except Exception as e:
        raise HTTPException(status_code=424, detail=str(e))

    raw_values = _filter_raw_values(raw_values, start_dt, end_dt)

    # Step 1: hourly averaging
    hourly_values = hourly_average(raw_values)

    level2 = _aggregate_level2(hourly_values)
    level1 = _aggregate_level1(level2)

    categories = format_categories(flatten_level2(level2))
    total_generation = sum(level1.values())
    renewable_share = (
        round((level1["renewables"] / total_generation) * 100, 2)
        if total_generation else 0
    )

    return {
        "start_date": to_iso_date(start_dt),
        "end_date": to_iso_date(end_dt),
        "filter": _infer_filter(start_dt, end_dt),
        "level1": level1,
        "level2": level2,
        "total_generation": total_generation,
        "renewable_share_percent": renewable_share,
        "categories": categories,
        "tooltip": (
            "The pie chart shows Israel's electricity generation mix and illustrates "
            "the different energy sources: fossil (coal, natural gas, diesel), "
            "renewables (photovoltaic, biogas, wind, solar-thermal, photovoltaic with storage), "
            "and other (other, pumped storage). Data are updated hourly from the NOGA system operator."
        ),
    }


# ----------------------------------------------------------
# EXPORT TO EXCEL (XLSX)
# ----------------------------------------------------------
@router.get("/production-mix/export")
async def export_energy_mix(
    start_date: str = None,
    end_date: str = None
):

    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=DEFAULT_RANGE_DAYS)

    raw_values = await NogaService.fetch_production_mix(
        to_noga_date(start_dt),
        to_noga_date(end_dt),
        NOGA_TOKEN,
    )
    hourly_values = hourly_average(raw_values)
    level2 = _aggregate_level2(hourly_values)
    level1 = _aggregate_level1(level2)
    total = sum(level1.values())

    # Build Excel with summary + detailed sheets
    buffer = BytesIO()
    df_level1 = pd.DataFrame(
        [{"Category": k, "Value": v, "Percentage": round((v / total) * 100, 2) if total else 0}
         for k, v in level1.items()]
    )

    detailed_rows = []
    for cat, items in level2.items():
        for sub, value in items.items():
            detailed_rows.append({
                "Category": cat,
                "Subcategory": sub,
                "Value": value,
                "Percentage": round((value / total) * 100, 2) if total else 0,
            })
    df_level2 = pd.DataFrame(detailed_rows)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_level1.to_excel(writer, sheet_name="Summary", index=False)
        df_level2.to_excel(writer, sheet_name="Detailed", index=False)

    buffer.seek(0)
    file_name = "production_mix.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )
