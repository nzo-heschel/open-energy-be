# app/api/v1/installed_capacity.py
"""
Delivery 2 – Endpoints 9, 10, 11: Installed Capacity of Renewable Energy Facilities.
Source: Electricity Authority – Connected Facilities CSV (mehubarim).
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.connected_facilities_service import ConnectedFacilitiesService

router = APIRouter(
    prefix="/renewables/installed-capacity",
    tags=["Installed Capacity (Delivery 2)"],
)


# ------------------------------------------------------------------
# Endpoint 9 – GET /api/v1/renewables/installed-capacity/cumulative
# ------------------------------------------------------------------
@router.get("/cumulative")
async def get_installed_capacity_cumulative(
    year: int | None = None,
    district: str | None = None,
    technology: str | None = None,
):
    """
    Delivery 2 – Row 16: Cumulative installed capacity of renewable energy facilities.
    הספק מותקן (מצטבר) של מתקנים לייצור אנרגיות מתחדשות
    """
    try:
        return ConnectedFacilitiesService.get_installed_capacity(
            year=year, district=district, technology=technology,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch installed capacity data: {exc}",
        ) from exc


@router.get("/cumulative/export")
async def export_installed_capacity_cumulative(
    year: int | None = None,
    district: str | None = None,
    technology: str | None = None,
):
    """Export cumulative installed capacity to Excel."""
    try:
        payload = ConnectedFacilitiesService.get_installed_capacity(
            year=year, district=district, technology=technology,
        )
        contents = ConnectedFacilitiesService.to_excel(payload)
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to export data: {exc}")

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=installed_capacity_cumulative.xlsx"},
    )


# ------------------------------------------------------------------
# Endpoint 10 – GET /api/v1/renewables/installed-capacity/growth
# ------------------------------------------------------------------
@router.get("/growth")
async def get_installed_capacity_growth(
    district: str | None = None,
    technology: str | None = None,
):
    """
    Delivery 2 – Row 17: Growth rate of cumulative installed capacity.
    הספק מותקן (מצטבר) של מתקנים לייצור אנרגיות מתחדשות - קצב גדילה
    """
    try:
        return ConnectedFacilitiesService.get_installed_capacity_growth(
            district=district, technology=technology,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch growth rate data: {exc}",
        ) from exc


@router.get("/growth/export")
async def export_installed_capacity_growth(
    district: str | None = None,
    technology: str | None = None,
):
    """Export installed capacity growth rate to Excel."""
    try:
        payload = ConnectedFacilitiesService.get_installed_capacity_growth(
            district=district, technology=technology,
        )
        contents = ConnectedFacilitiesService.to_excel(payload)
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to export data: {exc}")

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=installed_capacity_growth.xlsx"},
    )


# ------------------------------------------------------------------
# Endpoint 11 – GET /api/v1/renewables/installed-capacity/by-facility-size
# ------------------------------------------------------------------
@router.get("/by-facility-size")
async def get_capacity_by_facility_size(
    year: int | None = None,
    district: str | None = None,
):
    """
    Delivery 2 – Row 18: Facility capacity connected over time, by facility size.
    הספק מתקנים שחוברו על ציר זמן, לפי גודל מתקן
    """
    try:
        return ConnectedFacilitiesService.get_capacity_by_facility_size(
            year=year, district=district,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to fetch capacity by facility size: {exc}",
        ) from exc


@router.get("/by-facility-size/export")
async def export_capacity_by_facility_size(
    year: int | None = None,
    district: str | None = None,
):
    """Export capacity by facility size to Excel."""
    try:
        payload = ConnectedFacilitiesService.get_capacity_by_facility_size(
            year=year, district=district,
        )
        contents = ConnectedFacilitiesService.to_excel(payload)
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Failed to export data: {exc}")

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=capacity_by_facility_size.xlsx"},
    )
