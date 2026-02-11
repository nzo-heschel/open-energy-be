# app/api/v1/energy_overview.py
from datetime import datetime, timedelta
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.energy_overview_service import EnergyOverviewService
from app.utils.date_utils import resolve_date_range, to_iso_date

router = APIRouter(prefix="/energy", tags=["Energy Overview"])


def _resolve_overview_dates(start_date: str | None, end_date: str | None):
    """
    Use provided dates or default to the last 7 days.
    """
    if start_date and end_date:
        return resolve_date_range(start_date, end_date, default_days=365)

    today = datetime.now()
    return today - timedelta(days=7), today


def _infer_filter(start_dt, end_dt):
    days = (end_dt - start_dt).days
    if days <= 1:
        return "day"
    if days <= 31:
        return "month"
    if days <= 365:
        return "year"
    return "decade"


# --------------------------------------------------------
# MAIN OVERVIEW ENDPOINT
# --------------------------------------------------------
@router.get("/overview")
async def get_energy_overview(
    start_date: str = None,
    end_date: str = None
):
    """
    Delivery-1 Part-2:
    - Level-1
    - Level-2
    - % renewable
    - Period slicing
    - Hourly averaging
    """
    start_dt, end_dt = _resolve_overview_dates(start_date, end_date)
    iso_start, iso_end = to_iso_date(start_dt), to_iso_date(end_dt)
    result = await EnergyOverviewService.get_overview(iso_start, iso_end)
    return {
        "start_date": result.get("start_date"),
        "end_date": result.get("end_date"),
        "filter": _infer_filter(start_dt, end_dt),
        "categories": result.get("categories", []),
        "category_percentages": result.get("category_percentages", {}),
        "tooltip": result.get("tooltip"),
        "total": result.get("total"),
        "level1": result.get("level1"),
        "level2": result.get("level2"),
        "renewable_generation": result.get("renewable_generation"),
        "renewable_share_percent": result.get("renewable_share_percent"),
    }


# --------------------------------------------------------
# DETAILED HIERARCHY VIEW
# --------------------------------------------------------
@router.get("/overview/details")
async def get_overview_details(
    start_date: str = None,
    end_date: str = None
):
    start_dt, end_dt = _resolve_overview_dates(start_date, end_date)
    iso_start, iso_end = to_iso_date(start_dt), to_iso_date(end_dt)
    result = await EnergyOverviewService.get_overview(iso_start, iso_end)
    return {
        "start_date": result.get("start_date"),
        "end_date": result.get("end_date"),
        "filter": _infer_filter(start_dt, end_dt),
        "categories": result.get("categories", []),
    }


# --------------------------------------------------------
# EXPORT TO EXCEL
# --------------------------------------------------------
@router.get("/overview/export")
async def export_overview_energy(
    start_date: str = None,
    end_date: str = None
):
    start_dt, end_dt = _resolve_overview_dates(start_date, end_date)
    iso_start, iso_end = to_iso_date(start_dt), to_iso_date(end_dt)

    result = await EnergyOverviewService.get_overview(iso_start, iso_end)
    contents = EnergyOverviewService.to_excel_bytes(result)

    file_name = "energy_overview.xlsx"

    return StreamingResponse(
        iter([contents]),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )
