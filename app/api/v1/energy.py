# app/api/v1/energy.py
import os
from enum import Enum
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from app.services.noga_service import NogaService
from app.utils.date_utils import resolve_date_range, to_iso_date, to_noga_date
from app.utils.response_formatter import flatten_level2, format_categories

load_dotenv()

router = APIRouter(prefix="/energy", tags=["Energy"])
# Keep default windows small to avoid slow/broken proxy downloads; override via env if needed.
DEFAULT_RANGE_DAYS = int(os.getenv("ENERGY_PRODUCTION_MIX_DEFAULT_DAYS", "365"))


class Granularity(str, Enum):
    """
    Controls how the production-mix series is grouped for the line chart.
    """

    DAY = "day"     # hourly points
    MONTH = "month" # daily points
    YEAR = "year"   # monthly points


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
        "Non-renewables": {
            "coal": sum(v.get("coal", 0) for v in hourly_values),
            "natural_gas": sum(v.get("natural_Gas", 0) for v in hourly_values),
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
    return level2


def _aggregate_level1(level2: Dict) -> Dict:
    return {
        "Non-renewables": sum(level2["Non-renewables"].values()),
        "Renewables": sum(level2["Renewables"].values()),
        "Other": sum(level2["Other"].values()),
    }


def _infer_filter(start_dt, end_dt):
    days = (end_dt - start_dt).days
    if days <= 1:
        return "day"
    if days <= 31:
        return "month"
    return "year"


def _default_days_for_view(view: Granularity) -> int:
    """
    When no explicit dates are passed, pick a sane default window per view to avoid oversized payloads.
    """
    if view == Granularity.DAY:
        return 1
    if view == Granularity.MONTH:
        return 31
    return DEFAULT_RANGE_DAYS


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


def _bucket_time_series(hourly_values: List[Dict], view: Granularity) -> List[Dict]:
    """
    Build time-series points for the line chart according to the selected granularity.
    - day   -> hourly points
    - month -> daily points
    - year  -> monthly points
    """
    buckets: Dict[str, Dict] = {}

    for hv in hourly_values:
        hour_str = hv.get("hour")
        if not hour_str:
            continue
        try:
            ts = datetime.strptime(hour_str, "%d-%m-%Y %H")
        except Exception:
            continue

        if view == Granularity.DAY:
            sort_key = ts
            period = ts.strftime("%Y-%m-%dT%H:00")
            label = ts.strftime("%H:%M")
        elif view == Granularity.MONTH:
            sort_key = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            period = sort_key.strftime("%Y-%m-%d")
            label = sort_key.strftime("%d %b")
        else:
            sort_key = ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period = sort_key.strftime("%Y-%m")
            label = sort_key.strftime("%b %Y")

        bucket = buckets.setdefault(
            period,
            {
                "_sort_key": sort_key,
                "label": label,
                "non_renewables": 0.0,
                "renewables": 0.0,
                "other": 0.0,
            },
        )

        bucket["non_renewables"] += (
            hv.get("coal", 0)
            + hv.get("natural_Gas", 0)
            + hv.get("mazut", 0)
        )
        bucket["renewables"] += (
            hv.get("photoVoltaic", 0)
            + hv.get("bio_Gas", 0)
            + hv.get("wind", 0)
            + hv.get("termo_Soler", 0)
            + hv.get("photovoltaicIntegrated", 0)
        )
        bucket["other"] += hv.get("other", 0) + hv.get("pumpedStorage", 0)

    series: List[Dict] = []
    for bucket in sorted(buckets.values(), key=lambda b: b["_sort_key"]):
        total = bucket["non_renewables"] + bucket["renewables"] + bucket["other"]
        non_renewables_share = round((bucket["non_renewables"] / total) * 100, 2) if total else 0
        renewables_share = round((bucket["renewables"] / total) * 100, 2) if total else 0
        other_share = round((bucket["other"] / total) * 100, 2) if total else 0
        series.append(
            {
                "period": bucket["_sort_key"].strftime("%Y-%m-%dT%H:00")
                if view == Granularity.DAY
                else bucket["_sort_key"].strftime("%Y-%m-%d")
                if view == Granularity.MONTH
                else bucket["_sort_key"].strftime("%Y-%m"),
                "label": bucket["label"],
                "non_renewables_mw": round(bucket["non_renewables"], 2),
                "renewables_mw": round(bucket["renewables"], 2),
                "other_mw": round(bucket["other"], 2),
                "total_mw": round(total, 2),
                "non_renewables_share_percent": non_renewables_share,
                "renewables_share_percent": renewables_share,
                "other_share_percent": other_share,
                "renewable_share_percent": renewables_share,  # backward-friendly alias
            }
        )

    return series


# --------------------------
# MAIN ENDPOINT
# --------------------------
@router.get("/production-mix")
async def get_production_mix(
    start_date: str = None,
    end_date: str = None,
    granularity: Granularity | None = Query(
        default=None,
        description="Group the time series by day (hourly points), month (daily points), or year (monthly points).",
    ),
) -> Dict:
    """
    Returns Israel's electricity production mix.
    - Level1/Level2 for pies (existing behavior).
    - Time series bucketed by the requested granularity for the line chart.
    """

    # Choose granularity first, then derive a default range that matches it when dates are omitted.
    tentative_start, tentative_end = resolve_date_range(start_date, end_date, default_days=DEFAULT_RANGE_DAYS)
    view = granularity or Granularity(_infer_filter(tentative_start, tentative_end))
    start_dt, end_dt = resolve_date_range(
        start_date,
        end_date,
        default_days=_default_days_for_view(view),
    )

    noga_token = os.getenv("NOGA_API_TOKEN")
    try:
        raw_values = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            noga_token,
        )
    except Exception as e:
        raise HTTPException(status_code=424, detail=str(e))

    raw_values = _filter_raw_values(raw_values, start_dt, end_dt)

    # Step 1: hourly averaging
    hourly_values = hourly_average(raw_values)
    series = _bucket_time_series(hourly_values, view)

    level2 = _aggregate_level2(hourly_values)
    level1 = _aggregate_level1(level2)

    categories = format_categories(flatten_level2(level2))
    total_generation = sum(level1.values())
    renewable_share = (
        round((level1["Renewables"] / total_generation) * 100, 2)
        if total_generation else 0
    )

    return {
        "start_date": to_iso_date(start_dt),
        "end_date": to_iso_date(end_dt),
        "filter": view.value,
        "level1": level1,
        "level2": level2,
        "total_generation": total_generation,
        "renewable_share_percent": renewable_share,
        "categories": categories,
        "series_granularity": view.value,
        "series_units": "MW averaged from 5-minute NOGA samples (summed per bucket).",
        "series": series,
        "tooltip": (
            "Israel's electricity generation mix. Time series points are aggregated by the chosen view "
            "(day=hourly, month=daily, year=monthly). Each point sums 5-minute samples, converts them to hourly "
            "averages, and reports renewable share."
        ),
    }


# ----------------------------------------------------------
# EXPORT TO EXCEL (XLSX)
# ----------------------------------------------------------
@router.get("/production-mix/export")
async def export_energy_mix(
    start_date: str = None,
    end_date: str = None,
    granularity: Granularity | None = Query(
        default=None,
        description="Group the time series by day (hourly points), month (daily points), or year (monthly points).",
    ),
):

    tentative_start, tentative_end = resolve_date_range(start_date, end_date, default_days=DEFAULT_RANGE_DAYS)
    view = granularity or Granularity(_infer_filter(tentative_start, tentative_end))
    start_dt, end_dt = resolve_date_range(
        start_date,
        end_date,
        default_days=_default_days_for_view(view),
    )

    noga_token = os.getenv("NOGA_API_TOKEN")
    raw_values = await NogaService.fetch_production_mix(
        to_noga_date(start_dt),
        to_noga_date(end_dt),
        noga_token,
    )
    raw_values = _filter_raw_values(raw_values, start_dt, end_dt)
    hourly_values = hourly_average(raw_values)
    series = _bucket_time_series(hourly_values, view)
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
    df_series = pd.DataFrame(series)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_level1.to_excel(writer, sheet_name="Summary", index=False)
        df_level2.to_excel(writer, sheet_name="Detailed", index=False)
        df_series.to_excel(writer, sheet_name="Series", index=False)

    buffer.seek(0)
    file_name = "production_mix.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )
