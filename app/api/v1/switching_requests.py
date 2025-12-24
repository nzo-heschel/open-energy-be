# app/api/v1/switching_requests.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.switching_requests_service import build_payload, to_excel

router = APIRouter(prefix="/switching-requests", tags=["Switching Requests"])


@router.get("/")
async def get_switching_requests(customer_type: str | None = None, year: int | None = None):
    """
    Returns the four chart datasets for switching requests.
    - customer_type: residential | non_residential (optional filter)
    - year: optional year filter (>= 2021)
    """
    if customer_type and customer_type not in {"residential", "non_residential", "all"}:
        raise HTTPException(
            status_code=400,
            detail="customer_type must be residential or non_residential",
        )
    if year is not None and year < 2021:
        raise HTTPException(status_code=400, detail="year must be 2021 or later")

    try:
        payload = build_payload(customer_type=customer_type if customer_type != "all" else None, year=year)
        return payload
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=424, detail=str(exc))


@router.get("/export")
async def export_switching_requests(customer_type: str | None = None, year: int | None = None):
    """
    Export the filtered switching requests to Excel.
    """
    if customer_type and customer_type not in {"residential", "non_residential", "all"}:
        raise HTTPException(
            status_code=400,
            detail="customer_type must be residential or non_residential",
        )
    if year is not None and year < 2021:
        raise HTTPException(status_code=400, detail="year must be 2021 or later")

    try:
        payload = build_payload(customer_type=customer_type if customer_type != "all" else None, year=year)
        contents = to_excel(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=424, detail=str(exc))

    selected_year = payload.get("filter", {}).get("year") or "all"
    filename = f"switching_requests_{selected_year}.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
