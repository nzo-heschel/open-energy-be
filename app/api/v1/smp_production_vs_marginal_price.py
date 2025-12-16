import os
from fastapi import APIRouter, HTTPException

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
