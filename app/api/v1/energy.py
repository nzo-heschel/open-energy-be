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
DEFAULT_RANGE_DAYS = int(os.getenv("ENERGY_PRODUCTION_MIX_DEFAULT_DAYS", "7"))
MONTH_VIEW_DEFAULT_DAYS = int(os.getenv("ENERGY_PRODUCTION_MIX_MONTH_DAYS", "7"))
YEAR_VIEW_DEFAULT_DAYS = int(os.getenv("ENERGY_PRODUCTION_MIX_YEAR_DAYS", "3650"))


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


def _sum_keys(entry: Dict, keys: List[str]) -> float:
    return sum(entry.get(k, 0) or 0 for k in keys)


# Source key variants to keep fossil/renewable categories complete.
COAL_KEYS = ["coal"]
NATURAL_GAS_KEYS = ["natural_Gas", "natural_gas"]
DIESEL_KEYS = ["mazut", "diesel", "Diesel"]
PHOTOVOLTAIC_KEYS = ["photoVoltaic", "photovoltaic", "photo_voltaic"]
BIOGAS_KEYS = ["bio_Gas", "biogas"]
WIND_KEYS = ["wind"]
SOLAR_THERMAL_KEYS = ["termo_Soler", "solar", "solar_thermal"]
PV_STORAGE_KEYS = [
    "photovoltaicIntegrated",
    "pv_storage",
    "photovoltaic_storage",
    "storage",
    "batteries",
    "pumpedStorageBattery",
]
OTHER_KEYS = ["other"]
PUMPED_STORAGE_KEYS = ["pumpedStorage", "pumped_storage"]


def _aggregate_level2(hourly_values):
    """
    Aggregate hourly values into Delivery-1 Level-2 buckets.
    """
    level2 = {
        "Non-renewables": {
            "coal": sum(_sum_keys(v, COAL_KEYS) for v in hourly_values),
            "natural_gas": sum(_sum_keys(v, NATURAL_GAS_KEYS) for v in hourly_values),
            "diesel": sum(_sum_keys(v, DIESEL_KEYS) for v in hourly_values),
        },
        "Renewables": {
            "photoVoltaic": sum(_sum_keys(v, PHOTOVOLTAIC_KEYS) for v in hourly_values),
            "biogas": sum(_sum_keys(v, BIOGAS_KEYS) for v in hourly_values),
            "wind": sum(_sum_keys(v, WIND_KEYS) for v in hourly_values),
            "solar_thermal": sum(_sum_keys(v, SOLAR_THERMAL_KEYS) for v in hourly_values),
            "pv_storage": sum(_sum_keys(v, PV_STORAGE_KEYS) for v in hourly_values),
        },
        "Other": {
            "other": sum(_sum_keys(v, OTHER_KEYS) for v in hourly_values),
            "pumped_storage": sum(_sum_keys(v, PUMPED_STORAGE_KEYS) for v in hourly_values),
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
        return MONTH_VIEW_DEFAULT_DAYS
    return YEAR_VIEW_DEFAULT_DAYS


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
                "level2": {
                    "Non-renewables": {"coal": 0.0, "natural_gas": 0.0, "diesel": 0.0},
                    "Renewables": {"photoVoltaic": 0.0, "biogas": 0.0, "wind": 0.0, "solar_thermal": 0.0, "pv_storage": 0.0},
                    "Other": {"other": 0.0, "pumped_storage": 0.0},
                },
            },
        )

        # Top-level aggregates
        coal_v = _sum_keys(hv, COAL_KEYS)
        natural_gas_v = _sum_keys(hv, NATURAL_GAS_KEYS)
        mazut_v = _sum_keys(hv, DIESEL_KEYS)
        photo_v = _sum_keys(hv, PHOTOVOLTAIC_KEYS)
        bio_gas_v = _sum_keys(hv, BIOGAS_KEYS)
        wind_v = _sum_keys(hv, WIND_KEYS)
        termo_v = _sum_keys(hv, SOLAR_THERMAL_KEYS)
        pv_integrated_v = _sum_keys(hv, PV_STORAGE_KEYS)
        other_v = _sum_keys(hv, OTHER_KEYS)
        pumped_v = _sum_keys(hv, PUMPED_STORAGE_KEYS)

        bucket["non_renewables"] += coal_v + natural_gas_v + mazut_v
        bucket["renewables"] += photo_v + bio_gas_v + wind_v + termo_v + pv_integrated_v
        bucket["other"] += other_v + pumped_v

        # Per-period Level-2 breakdown (keys match `_aggregate_level2` output)
        bucket["level2"]["Non-renewables"]["coal"] += coal_v
        bucket["level2"]["Non-renewables"]["natural_gas"] += natural_gas_v
        bucket["level2"]["Non-renewables"]["diesel"] += mazut_v

        bucket["level2"]["Renewables"]["photoVoltaic"] += photo_v
        bucket["level2"]["Renewables"]["biogas"] += bio_gas_v
        bucket["level2"]["Renewables"]["wind"] += wind_v
        bucket["level2"]["Renewables"]["solar_thermal"] += termo_v
        bucket["level2"]["Renewables"]["pv_storage"] += pv_integrated_v

        bucket["level2"]["Other"]["other"] += other_v
        bucket["level2"]["Other"]["pumped_storage"] += pumped_v

    series: List[Dict] = []
    for bucket in sorted(buckets.values(), key=lambda b: b["_sort_key"]):
        total = bucket["non_renewables"] + bucket["renewables"] + bucket["other"]
        non_renewables_share = round((bucket["non_renewables"] / total) * 100, 2) if total else 0
        renewables_share = round((bucket["renewables"] / total) * 100, 2) if total else 0
        other_share = round((bucket["other"] / total) * 100, 2) if total else 0
        level2_flat = {
            "coal_mw": round(bucket["level2"]["Non-renewables"]["coal"], 2),
            "natural_gas_mw": round(bucket["level2"]["Non-renewables"]["natural_gas"], 2),
            "diesel_mw": round(bucket["level2"]["Non-renewables"]["diesel"], 2),
            "photoVoltaic_mw": round(bucket["level2"]["Renewables"]["photoVoltaic"], 2),
            "biogas_mw": round(bucket["level2"]["Renewables"]["biogas"], 2),
            "wind_mw": round(bucket["level2"]["Renewables"]["wind"], 2),
            "solar_thermal_mw": round(bucket["level2"]["Renewables"]["solar_thermal"], 2),
            "pv_storage_mw": round(bucket["level2"]["Renewables"]["pv_storage"], 2),
            "other_source_mw": round(bucket["level2"]["Other"]["other"], 2),
            "pumped_storage_mw": round(bucket["level2"]["Other"]["pumped_storage"], 2),
        }
        # Include per-period Level-2 breakdown alongside top-level aggregates
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
                **level2_flat,
                "level2": {
                    "Non-renewables": {
                        "coal": round(bucket["level2"]["Non-renewables"]["coal"], 2),
                        "natural_gas": round(bucket["level2"]["Non-renewables"]["natural_gas"], 2),
                        "diesel": round(bucket["level2"]["Non-renewables"]["diesel"], 2),
                    },
                    "Renewables": {
                        "photoVoltaic": round(bucket["level2"]["Renewables"]["photoVoltaic"], 2),
                        "biogas": round(bucket["level2"]["Renewables"]["biogas"], 2),
                        "wind": round(bucket["level2"]["Renewables"]["wind"], 2),
                        "solar_thermal": round(bucket["level2"]["Renewables"]["solar_thermal"], 2),
                        "pv_storage": round(bucket["level2"]["Renewables"]["pv_storage"], 2),
                    },
                    "Other": {
                        "other": round(bucket["level2"]["Other"]["other"], 2),
                        "pumped_storage": round(bucket["level2"]["Other"]["pumped_storage"], 2),
                    },
                },
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
