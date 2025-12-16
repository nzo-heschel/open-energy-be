# app/api/v1/renewable_transition.py
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.renewable_transition_service import RenewableTransitionService

router = APIRouter(prefix="/renewables", tags=["Renewable Energy Transition"])

NOGA_TOKEN = os.getenv("NOGA_API_TOKEN")


def _resolve_year(year: str | None) -> int:
    if year is None or str(year).strip() == "":
        default_year_str = os.getenv("RENEWABLE_TRANSITION_DEFAULT_YEAR")
        if default_year_str:
            try:
                return int(default_year_str)
            except Exception:
                pass
        from datetime import datetime
        return datetime.now().year
    try:
        return int(year)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid year. Provide a 4-digit year.")


@router.get("/transition")
async def get_renewable_transition(year: str | None = None):
    """
    Delivery 2 - Item 2: Transition to renewable energies in Israel (daily renewable generation totals).
    """
    resolved_year = _resolve_year(year)
    try:
        return await RenewableTransitionService.get_transition(resolved_year, NOGA_TOKEN)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch renewable transition data: {exc}",
        ) from exc


@router.get("/transition/export")
async def export_renewable_transition(year: str | None = None):
    resolved_year = _resolve_year(year)
    result = await RenewableTransitionService.get_transition(resolved_year, NOGA_TOKEN)
    contents = RenewableTransitionService.to_excel(result.get("series", []), result.get("totals", {}))
    file_name = f"renewable_transition_{resolved_year}.xlsx"

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )
