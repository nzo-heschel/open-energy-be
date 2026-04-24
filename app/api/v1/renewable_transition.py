# app/api/v1/renewable_transition.py
import os
from typing import List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.renewable_transition_service import RenewableTransitionService
from app.utils.date_utils import resolve_date_range

router = APIRouter(prefix="/renewables", tags=["Renewable Energy Transition"])

NOGA_TOKEN = os.getenv("NOGA_API_TOKEN")


@router.get("/transition")
async def get_renewable_transition(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Delivery 2 - Item 2: Transition to renewable energies in Israel.
    Shows monthly renewable share (%) with per-year overlay.
    Uses start_date/end_date for filtering (no separate year filter).
    Response includes years_data for clickable year highlighting.
    Y-axis unit: [%] (renewable_share_percent).
    """
    try:
        return await RenewableTransitionService.get_transition(
            start_date=start_date,
            end_date=end_date,
            token=NOGA_TOKEN,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch renewable transition data: {exc}",
        ) from exc


@router.get("/transition/export")
async def export_renewable_transition(
    start_date: str | None = None,
    end_date: str | None = None,
):
    result = await RenewableTransitionService.get_transition(
        start_date=start_date,
        end_date=end_date,
        token=NOGA_TOKEN,
    )
    contents = RenewableTransitionService.to_excel(
        result.get("monthly_series", []),
        result.get("totals", {}),
    )
    file_name = "renewable_transition.xlsx"

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )
