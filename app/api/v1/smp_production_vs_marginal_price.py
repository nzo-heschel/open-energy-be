import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.smp_production_service import SMPProductionService
from app.utils.date_utils import resolve_date_range

router = APIRouter(prefix="/energy/smp-production-vs-marginal-price", tags=["SMP Production vs Marginal Price"])


@router.get("/")
async def get_smp_production_vs_marginal_price(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Returns SMP, net demand, combined view, and correlation dataset for the requested range.
    """
    smp_token = os.getenv("SMP_TOKEN") or os.getenv("NOGA_API_TOKEN")
    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=1)
    try:
        payload = await SMPProductionService.fetch_and_process(start_dt, end_dt, smp_token)
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to process SMP vs marginal price: {exc}")


@router.get("/export")
async def export_smp_production_vs_marginal_price(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Export SMP production vs marginal price response to Excel.
    """
    smp_token = os.getenv("SMP_TOKEN") or os.getenv("NOGA_API_TOKEN")
    start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=1)
    try:
        payload = await SMPProductionService.fetch_and_process(start_dt, end_dt, smp_token)
        contents = SMPProductionService.to_excel(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to export SMP vs marginal price: {exc}")

    filename = f"smp_production_vs_marginal_price_{payload['start_date']}_to_{payload['end_date']}.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
