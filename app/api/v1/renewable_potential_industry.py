# app/api/v1/renewable_potential_industry.py
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.renewable_potential_industry_service import (
    RenewablePotentialIndustryService,
)
from app.utils.date_utils import resolve_date_range

router = APIRouter(prefix="/renewables", tags=["Renewable Potential by Industry"])

NOGA_TOKEN = os.getenv("NOGA_API_TOKEN")


@router.get("/potential-by-industry")
async def get_renewable_potential_by_industry(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Delivery 2 - Item 3: Potential renewable production by industry type (solar, wind, biogas), daily totals.
    Uses start_date/end_date filtering instead of year filter.
    """
    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=365)
    try:
        return await RenewablePotentialIndustryService.get_potential(
            start_dt=start_dt,
            end_dt=end_dt,
            token=NOGA_TOKEN,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch renewable potential by industry: {exc}",
        ) from exc


@router.get("/potential-by-industry/export")
async def export_renewable_potential_by_industry(
    start_date: str | None = None,
    end_date: str | None = None,
):
    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=365)
    result = await RenewablePotentialIndustryService.get_potential(
        start_dt=start_dt,
        end_dt=end_dt,
        token=NOGA_TOKEN,
    )
    contents = RenewablePotentialIndustryService.to_excel(result.get("series", []), result.get("totals", {}))
    file_name = "renewable_potential_industry.xlsx"

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )
