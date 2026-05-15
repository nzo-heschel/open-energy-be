# app/api/v1/response_capacity.py
"""
Delivery 2 – Endpoints 12, 13, 14: Response Capacity (Distributor Responses).
Source: Electricity Authority – Distributor Responses CSV (teshuvotmehalek).
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.distributor_responses_service import DistributorResponsesService

router = APIRouter(
    prefix="/renewables/response-capacity",
    tags=["Response Capacity (Delivery 2)"],
)


# ------------------------------------------------------------------
# Endpoint 12 – GET /api/v1/renewables/response-capacity/by-period
# ------------------------------------------------------------------
@router.get("/by-period")
async def get_response_capacity_by_period(
    year: int | None = None,
    district: str | None = None,
    technology: str | None = None,
    response_type: str | None = None,
    include_cancelled: bool = True,
):
    """
    Delivery 2 – Row 19: Response capacity divided by time period.
    הספק תשובות מחלק לפי תקופה

    Filters:
      - year: Filter to a specific year
      - district: Filter by district (e.g. Jerusalem, North, South, Haifa, Center, Tel Aviv)
      - technology: Filter by technology (Photovoltaic, Wind, Other)
      - response_type: Filter by response (Positive, Partial Positive, Limited Positive, Negative)
      - include_cancelled: Include cancelled orders (default: true, matches manual file sums)
    """
    try:
        return DistributorResponsesService.get_response_capacity_by_period(
            year=year,
            district=district,
            technology=technology,
            response_type=response_type,
            include_cancelled=include_cancelled,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch response capacity by period: {exc}",
        ) from exc


@router.get("/by-period/export")
async def export_response_capacity_by_period(
    year: int | None = None,
    district: str | None = None,
    technology: str | None = None,
    response_type: str | None = None,
    include_cancelled: bool = True,
):
    """Export response capacity by period to Excel."""
    try:
        payload = DistributorResponsesService.get_response_capacity_by_period(
            year=year,
            district=district,
            technology=technology,
            response_type=response_type,
            include_cancelled=include_cancelled,
        )
        contents = DistributorResponsesService.to_excel(payload)
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to export data: {exc}")

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=response_capacity_by_period.xlsx"},
    )


# ------------------------------------------------------------------
# Endpoint 13 – GET /api/v1/renewables/response-capacity/by-size
# ------------------------------------------------------------------
@router.get("/by-size")
async def get_response_capacity_by_size(
    year: int | None = None,
    district: str | None = None,
    response_type: str | None = "Positive",
    include_cancelled: bool = True,
):
    """
    Delivery 2 – Row 20: Response capacity divided by facility size (kilowatt).
    הספק תשובת מחולק לפי גודל מתקן (קילוואט)

    NOTE: Defaults to Positive responses only (client requirement for Diagram 5.2).
    Pass response_type=all to get all response types.
    """
    try:
        # Allow overriding to "all" to fetch every response type
        rt = None if response_type and response_type.lower() == "all" else response_type
        return DistributorResponsesService.get_response_capacity_by_size(
            year=year,
            district=district,
            response_type=rt,
            include_cancelled=include_cancelled,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch response capacity by size: {exc}",
        ) from exc


@router.get("/by-size/export")
async def export_response_capacity_by_size(
    year: int | None = None,
    district: str | None = None,
    response_type: str | None = "Positive",
    include_cancelled: bool = True,
):
    """Export response capacity by facility size to Excel."""
    try:
        rt = None if response_type and response_type.lower() == "all" else response_type
        payload = DistributorResponsesService.get_response_capacity_by_size(
            year=year,
            district=district,
            response_type=rt,
            include_cancelled=include_cancelled,
        )
        contents = DistributorResponsesService.to_excel(payload)
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to export data: {exc}")

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=response_capacity_by_size.xlsx"},
    )


# ------------------------------------------------------------------
# Endpoint 14 – GET /api/v1/renewables/response-capacity/by-district
# ------------------------------------------------------------------
@router.get("/by-district")
async def get_response_capacity_by_district(
    year: int | None = None,
    technology: str | None = None,
    include_cancelled: bool = True,
):
    """
    Delivery 2 – Row 21: Response capacity divided by district.
    הספק תשובת מחולק לפי מחוז
    """
    try:
        return DistributorResponsesService.get_response_capacity_by_district(
            year=year,
            technology=technology,
            include_cancelled=include_cancelled,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch response capacity by district: {exc}",
        ) from exc


@router.get("/by-district/export")
async def export_response_capacity_by_district(
    year: int | None = None,
    technology: str | None = None,
    include_cancelled: bool = True,
):
    """Export response capacity by district to Excel."""
    try:
        payload = DistributorResponsesService.get_response_capacity_by_district(
            year=year,
            technology=technology,
            include_cancelled=include_cancelled,
        )
        contents = DistributorResponsesService.to_excel(payload)
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to export data: {exc}")

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=response_capacity_by_district.xlsx"},
    )
