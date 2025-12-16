# app/api/v1/renewable_potential_industry.py
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.renewable_potential_industry_service import (
    RenewablePotentialIndustryService,
)

router = APIRouter(prefix="/renewables", tags=["Renewable Potential by Industry"])

NOGA_TOKEN = os.getenv("NOGA_API_TOKEN")


def _resolve_year(year: str | None) -> int:
    if year is None or str(year).strip() == "":
        default_year_str = os.getenv("RENEWABLE_POTENTIAL_DEFAULT_YEAR")
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


@router.get("/potential-by-industry")
async def get_renewable_potential_by_industry(year: str | None = None):
    """
    Delivery 2 - Item 3: Potential renewable production by industry type (solar, wind, biogas), daily totals.
    """
    resolved_year = _resolve_year(year)
    try:
        return await RenewablePotentialIndustryService.get_potential(resolved_year, NOGA_TOKEN)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch renewable potential by industry: {exc}",
        ) from exc


@router.get("/potential-by-industry/export")
async def export_renewable_potential_by_industry(year: str | None = None):
    resolved_year = _resolve_year(year)
    result = await RenewablePotentialIndustryService.get_potential(resolved_year, NOGA_TOKEN)
    contents = RenewablePotentialIndustryService.to_excel(result.get("series", []), result.get("totals", {}))
    file_name = f"renewable_potential_industry_{resolved_year}.xlsx"

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )
