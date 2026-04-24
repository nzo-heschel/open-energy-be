# app/api/v1/renewable_mix.py
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.renewable_mix_service import RenewableMixService
from app.utils.date_utils import resolve_date_range

router = APIRouter(prefix="/renewables", tags=["Renewable Energy Mix"])

DEFAULT_RANGE_DAYS = int(os.getenv("RENEWABLE_MIX_DEFAULT_DAYS", "30"))
NOGA_TOKEN = os.getenv("NOGA_API_TOKEN")


@router.get("/production-mix")
async def get_renewable_production_mix(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
):
    """
    Delivery 2 - Item 1: Renewable energy production mix (solar, wind, biogas).
    Supports category filter: solar | wind | other.
    No year filter — use start_date and end_date for date range filtering.
    """
    category_filter = None
    if category:
        category_lower = category.lower()
        if category_lower not in {"solar", "wind", "other"}:
            raise HTTPException(status_code=400, detail="Invalid category. Use solar, wind, or other.")
        category_filter = category_lower

    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=DEFAULT_RANGE_DAYS)
    try:
        return await RenewableMixService.get_mix(start_dt, end_dt, NOGA_TOKEN, category_filter)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch renewable production mix: {exc}",
        ) from exc


@router.get("/production-mix/export")
async def export_renewable_production_mix(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
):
    category_filter = None
    if category:
        category_lower = category.lower()
        if category_lower not in {"solar", "wind", "other"}:
            raise HTTPException(status_code=400, detail="Invalid category. Use solar, wind, or other.")
        category_filter = category_lower

    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=DEFAULT_RANGE_DAYS)
    result = await RenewableMixService.get_mix(start_dt, end_dt, NOGA_TOKEN, category_filter)
    contents = RenewableMixService.to_excel(result.get("series", []), result.get("totals", {}))
    file_name = "renewable_production_mix.xlsx"

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )
