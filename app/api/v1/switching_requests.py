# app/api/v1/switching_requests.py
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.switching_requests_service import build_payload, to_excel

router = APIRouter(prefix="/switching-requests", tags=["Switching Requests"])


def _parse_years(year: list[str] | None) -> list[int]:
    """Flatten the ``year`` query param into a list of ints.

    Accepts repeated params (?year=2021&year=2022) and comma-separated
    values (?year=2021,2022) interchangeably so the FE can use either.
    Empty/None means "all years".
    """
    if not year:
        return []
    parsed: list[int] = []
    for raw in year:
        for part in str(raw).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                parsed.append(int(part))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid year value: {part!r}")
    return parsed


@router.get("/")
async def get_switching_requests(
    customer_type: str | None = None,
    year: list[str] | None = Query(default=None),
):
    """
    Returns the four chart datasets for switching requests.
    - customer_type: residential | non_residential (optional filter)
    - year: optional year filter (>= 2021). Multi-select supported:
      repeat the param (?year=2021&year=2022) or comma-separate
      (?year=2021,2022). Omit entirely to show ALL years (default).
    """
    if customer_type and customer_type not in {"residential", "non_residential", "all"}:
        raise HTTPException(
            status_code=400,
            detail="customer_type must be residential or non_residential",
        )
    selected_years = _parse_years(year)
    invalid = [y for y in selected_years if y < 2021]
    if invalid:
        raise HTTPException(status_code=400, detail="year must be 2021 or later")

    try:
        payload = build_payload(
            customer_type=customer_type if customer_type != "all" else None,
            years=selected_years or None,
        )
        return payload
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=424, detail=str(exc))


@router.get("/export")
async def export_switching_requests(
    customer_type: str | None = None,
    year: list[str] | None = Query(default=None),
):
    """
    Export the filtered switching requests to Excel.
    """
    if customer_type and customer_type not in {"residential", "non_residential", "all"}:
        raise HTTPException(
            status_code=400,
            detail="customer_type must be residential or non_residential",
        )
    selected_years = _parse_years(year)
    invalid = [y for y in selected_years if y < 2021]
    if invalid:
        raise HTTPException(status_code=400, detail="year must be 2021 or later")

    try:
        payload = build_payload(
            customer_type=customer_type if customer_type != "all" else None,
            years=selected_years or None,
        )
        contents = to_excel(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=424, detail=str(exc))

    yr_filter = payload.get("filter", {}).get("years")
    selected_year = "_".join(str(y) for y in yr_filter) if isinstance(yr_filter, list) and yr_filter else "all"
    filename = f"switching_requests_{selected_year}.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
