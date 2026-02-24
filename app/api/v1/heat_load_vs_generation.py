from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.heat_load_vs_generation_service import (
    HeatLoadView,
    HeatLoadVsGenerationService,
)
from app.utils.date_utils import resolve_date_range

router = APIRouter(
    prefix="/heat-load-vs-generation",
    tags=["Heat Load vs Electricity Generation"],
)


def _resolve_dates(start_date: Optional[str], end_date: Optional[str], view: HeatLoadView) -> tuple[datetime, datetime]:
    if start_date and end_date:
        return resolve_date_range(start_date, end_date, default_days=365)
    default_days = 365 if view == HeatLoadView.YEAR else 30
    return resolve_date_range(start_date, end_date, default_days=default_days)


@router.get("/")
async def get_heat_load_vs_generation(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: HeatLoadView = Query(
        default=HeatLoadView.YEAR,
        description="Filter: month (ticks by day), year (ticks by week), custom (between dates)",
    ),
):
    """
    Delivery-3 Endpoint 7:
    Heat load vs electricity generation.
    """
    try:
        start_dt, end_dt = _resolve_dates(start_date, end_date, view)
        result = await HeatLoadVsGenerationService.get_data(start_dt, end_dt, view)
        return result.payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to compute heat load vs generation: {exc}")


@router.get("/export")
async def export_heat_load_vs_generation(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    view: HeatLoadView = Query(
        default=HeatLoadView.YEAR,
        description="Filter: month (ticks by day), year (ticks by week), custom (between dates)",
    ),
):
    """
    Export heat load vs electricity generation to Excel.
    """
    start_dt, end_dt = _resolve_dates(start_date, end_date, view)
    result = await HeatLoadVsGenerationService.get_data(start_dt, end_dt, view)
    contents = HeatLoadVsGenerationService.to_excel_bytes(result)
    filename = f"heat_load_vs_generation_{result.payload['start_date']}_to_{result.payload['end_date']}.xlsx"

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
