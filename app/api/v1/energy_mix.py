import io
import pandas as pd
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from datetime import datetime
from app.services.noga_service import NogaService
from app.services.energy_mix_processor import EnergyMixProcessor

router = APIRouter()

# Helper function to calculate hourly average (last hour data)
def calculate_hourly_average(data):
    """
    Sum all values from the last hour and divide by 12.
    The data input is expected to be hourly production values for the last 12 hours.
    """
    total_production = sum(data)
    hourly_average = total_production / 12  # Average for the last hour
    return hourly_average

# -------------------------------------------------------------------
# 1️⃣ GET ENERGY MIX (MAIN ENDPOINT FOR FRONTEND PIE CHART)
# -------------------------------------------------------------------
@router.get("/production-mix")
async def get_energy_production_mix(
    filter: str = "this_year",
    start_date: str = None,
    end_date: str = None
):
    today = datetime.now()

    # --- Determine date range ---
    if filter == "today":
        start = today
        end = today
    elif filter == "this_month":
        start = today.replace(day=1)
        end = today
    elif filter == "this_year":
        start = today.replace(month=1, day=1)
        end = today
    elif filter == "this_decade":
        start = today.replace(year=today.year - 10, month=1, day=1)
        end = today
    elif filter == "between_dates":
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        start = today.replace(month=1, day=1)
        end = today

    # --- Fetch REAL data from NOGA ---
    raw_data = await NogaService.get_production_mix(start, end)

    # Assuming `raw_data` is a dictionary containing hourly data for energy production (mocked as 'hourly_data')
    hourly_data = raw_data.get('hourly_data', [])  # Example: ['coal', 'natural_gas', 'solar', ...]

    # --- Calculate hourly average ---
    if hourly_data:
        hourly_average = calculate_hourly_average(hourly_data)
    else:
        hourly_average = 0

    # --- Convert → categories + percentages ---
    result = EnergyMixProcessor.aggregate(raw_data)

    # Add the hourly average to the result
    result["hourly_average"] = hourly_average

    return result


# -------------------------------------------------------------------
# 2️⃣ EXPORT TO EXCEL
# -------------------------------------------------------------------
@router.get("/production-mix/export")
async def export_energy_mix_to_excel(
    filter: str = "this_year",
    start_date: str = None,
    end_date: str = None
):
    today = datetime.now()

    # --- Determine date range ---
    if filter == "today":
        start = today
        end = today
    elif filter == "this_month":
        start = today.replace(day=1)
        end = today
    elif filter == "this_year":
        start = today.replace(month=1, day=1)
        end = today
    elif filter == "this_decade":
        start = today.replace(year=today.year - 10, month=1, day=1)
        end = today
    elif filter == "between_dates":
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        start = today.replace(month=1, day=1)
        end = today

    # --- Fetch REAL data ---
    raw_data = await NogaService.get_production_mix(start, end)

    # --- Process the raw data ---
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
    filename = f"energy_production_mix_{filter}.xlsx"

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
