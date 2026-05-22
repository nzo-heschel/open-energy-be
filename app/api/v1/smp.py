# app/api/v1/smp.py
import os
from fastapi import APIRouter, HTTPException
from typing import Dict
from app.services.smp_service import SMPService
from app.services.smp_processor import SMPProcessor
from fastapi.responses import StreamingResponse
from app.services.demand_service import DemandService
from app.utils.date_utils import resolve_date_range, to_noga_date
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/energy/smp", tags=["SMP"])

@router.get("/")
async def get_smp_data(start_date: str = None, end_date: str = None) -> Dict:
    try:
        # Fetch token at request time so env changes apply without restart.
        smp_token = os.getenv("SMP_TOKEN") or os.getenv("NOGA_API_TOKEN")
        demand_token = os.getenv("DEMAND_TOKEN") or os.getenv("NOGA_API_TOKEN")
        start_dt, end_dt = resolve_date_range(start_date, end_date, default_days=1)
        raw_smp_data = await SMPService.fetch_smp_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            smp_token,
        )
        # Per client direction: NOGA is the primary source. Fetch demand via
        # DemandService (NOGA-first, NZO automatic fallback if NOGA fails).
        demand_data = await DemandService.fetch_demand_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            demand_token,
        )
        # SMP is half-hourly: pair each bin with the mean demand across the
        # same 30-min window (not a snapshot at the bin's start).
        demand_lookup = DemandService.to_demand_lookup(demand_data, window_minutes=30)
        # net_demand = demand − renewables. NZO-served demand carries
        # renewableSum per sample; NOGA's bare demand endpoint does not,
        # so fall back to the 5-min NZO energy stream for renewables in
        # the NOGA path. NEVER use NogaService.fetch_production_mix here:
        # its NZO branch returns hourly-summed values (~12× too big in a
        # 30-min window), which broke this chart in an earlier deploy.
        renewables_lookup = DemandService.to_renewables_lookup(demand_data, window_minutes=30)
        if not renewables_lookup:
            try:
                from app.services.nzo_fallback_service import NZOFallbackService
                from app.services.smp_production_service import SMPProductionService

                energy_rows = await NZOFallbackService.fetch_energy_data(
                    start_date=to_noga_date(start_dt),
                    end_date=to_noga_date(end_dt),
                    time_resolution="all",
                )
                renewables_lookup = SMPProductionService._build_renewables_window_lookup(
                    energy_rows, window_minutes=30
                )
            except Exception:
                renewables_lookup = {}

        days_delta = (end_dt - start_dt).days
        if days_delta <= 1:
            view = "day"
        elif days_delta <= 45:
            view = "month"
        else:
            view = "year"

        include_samples = view == "day"
        smp_data = SMPProcessor.process_smp_data(
            raw_smp_data,
            include_samples=include_samples,
            demand_lookup=demand_lookup,
            renewables_lookup=renewables_lookup,
        )
        has_prices = smp_data.get("chart_with_constraints") or smp_data.get("chart_without_constraints")
        if not has_prices:
            raise HTTPException(
                status_code=424,
                detail=(
                    "SMP price fields were not returned by the NOGA API. "
                    "Verify that the SMP endpoint is accessible with the provided subscription key."
                ),
            )

        days_delta = (end_dt - start_dt).days
        smp_data["view"] = view
        smp_data["start_date"] = start_dt.date().isoformat()
        smp_data["end_date"] = end_dt.date().isoformat()
        return smp_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=424, detail=f"Failed to fetch SMP data: {str(e)}")


@router.get("/export")
async def export_smp_data(start_date: str = None, end_date: str = None):
    """
    Export SMP response to Excel.
    """
    payload = await get_smp_data(start_date, end_date)
    contents = SMPProcessor.to_excel(payload)
    filename = f"smp_{payload['start_date']}_to_{payload['end_date']}.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
