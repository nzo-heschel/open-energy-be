# app/api/v1/switching_requests.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.switching_requests_service import build_payload, to_excel

router = APIRouter(prefix="/switching-requests", tags=["Switching Requests"])


@router.get("/")
async def get_switching_requests(customer_type: str | None = None):
    """
    Returns the four chart datasets for switching requests.
    - customer_type: residential | non_residential (optional filter)
    """
    if customer_type and customer_type not in {"residential", "non_residential"}:
        raise HTTPException(status_code=400, detail="customer_type must be residential or non_residential")

    try:
        payload = build_payload(customer_type=customer_type)
        return payload
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=424, detail=str(exc))


@router.get("/export")
async def export_switching_requests(customer_type: str | None = None):
    """
    Export the filtered switching requests to Excel.
    """
    if customer_type and customer_type not in {"residential", "non_residential"}:
        raise HTTPException(status_code=400, detail="customer_type must be residential or non_residential")

    try:
        payload = build_payload(customer_type=customer_type)
        contents = to_excel(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=424, detail=str(exc))

    filename = f"switching_requests_{payload['start_year']}.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
