# app/api/v1/energy_mix.py
import io
import os
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from app.services.noga_service import NogaService
from app.services.energy_mix_processor import EnergyMixProcessor
from app.utils.date_utils import resolve_date_range, to_iso_date, to_noga_date
from app.utils.response_formatter import flatten_level2, format_categories

router = APIRouter()
NOGA_TOKEN = os.getenv("NOGA_API_TOKEN", "7b397cafa75b4a00848542829a588dac")

# Helper function to calculate hourly average (last hour data)
def calculate_hourly_average(records):
    """
    Average total production over the last hour (last 12 samples).
    Expects a list of flattened NOGA records.
    """
    if not records:
        return 0

    last_samples = records[-12:]
    totals = []
    for sample in last_samples:
        total = sum(
            value
            for key, value in sample.items()
            if key not in ("date", "time") and isinstance(value, (int, float))
        )
        totals.append(total)

    return sum(totals) / len(totals) if totals else 0

# -------------------------------------------------------------------
# GET ENERGY MIX (MAIN ENDPOINT FOR FRONTEND PIE CHART)
# -------------------------------------------------------------------
@router.get("/production-mix")
async def get_energy_production_mix(
    start_date: str = None,
    end_date: str = None
):
    today = datetime.now()

    # Determine date range (default: start of year to today)
    if start_date and end_date:
        start_dt, end_dt = resolve_date_range(start_date, end_date)
    else:
        start_dt, end_dt = today.replace(month=1, day=1), today

    try:
        raw_data = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            NOGA_TOKEN,
        )
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to fetch production mix: {exc}")

    hourly_average = calculate_hourly_average(raw_data)
    result = EnergyMixProcessor.aggregate(raw_data)
    categories = format_categories(flatten_level2(result["level2"]))

    return {
        "start_date": to_iso_date(start_dt),
        "end_date": to_iso_date(end_dt),
        "hourly_average": hourly_average,
        "categories": categories,
    }


# -------------------------------------------------------------------
# EXPORT TO EXCEL
# -------------------------------------------------------------------
@router.get("/production-mix/export")
async def export_energy_mix_to_excel(
    start_date: str = None,
    end_date: str = None
):
    today = datetime.now()

    # Determine date range (default: start of year to today)
    if start_date and end_date:
        start_dt, end_dt = resolve_date_range(start_date, end_date)
    else:
        start_dt, end_dt = today.replace(month=1, day=1), today

    # Fetch REAL data
    try:
        raw_data = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            NOGA_TOKEN,
        )
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to fetch production mix: {exc}")

    # Process the raw data
    result = EnergyMixProcessor.aggregate(raw_data)

    # --- Create Excel File ---
    excel_buffer = io.BytesIO()

    df_level1 = pd.DataFrame(list(result["level1"].items()), columns=["Category", "Production"])
    df_level1["Percentage"] = df_level1["Category"].map(result["percentages"])

    detailed_rows = []
    for cat, items in result["level2"].items():
        for subcat, value in items.items():
            detailed_rows.append({
                "Category": cat,
                "Subcategory": subcat,
                "Production": value,
                "Percentage": round(value / result["total_production"] * 100, 2)
                if result["total_production"] > 0 else 0
            })

    df_level2 = pd.DataFrame(detailed_rows)

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df_level1.to_excel(writer, sheet_name="Summary", index=False)
        df_level2.to_excel(writer, sheet_name="Detailed", index=False)

    excel_buffer.seek(0)
    filename = "energy_production_mix.xlsx"

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
