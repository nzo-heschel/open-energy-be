# app/api/v1/delivery4_forecasts.py
"""Renewable forecast and international comparison endpoints."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.delivery4_forecasts_service import Delivery4ForecastsService

# Paths are mounted in main.py so these endpoints can use the public renewables
# namespace while keeping hidden backwards-compatible aliases.
router = APIRouter(tags=["Renewable Forecasts"])


def _get_payload(include_2050_targets: bool, include_solar_share: bool):
    try:
        return Delivery4ForecastsService.get_international_comparison(
            include_2050_targets=include_2050_targets,
            include_solar_share=include_solar_share,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to load international renewable comparison: {exc}",
        ) from exc


@router.get("/renewable-forecast-israel")
async def get_renewable_forecast_israel():
    """
    Israel renewable share forecast and targets.

    Values are percentages.
    """
    try:
        return Delivery4ForecastsService.get_israel_forecast()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to load Israel renewable forecast: {exc}",
        ) from exc


@router.get("/renewable-forecast-israel/export")
async def export_renewable_forecast_israel():
    """Excel export for Israel renewable forecast data."""
    try:
        payload = Delivery4ForecastsService.get_israel_forecast()
        contents = Delivery4ForecastsService.to_excel_diagram1(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Export failed: {exc}") from exc

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=renewable_forecast_israel.xlsx"},
    )


@router.get("/international-renewable-comparison")
async def get_international_renewable_comparison(
    include_2050_targets: bool = Query(
        default=True,
        description="Include 2050 renewable target series. 2030 is always included.",
    ),
    include_solar_share: bool = Query(
        default=True,
        description="Include 2024 solar share series.",
    ),
):
    """
    International renewable share and target comparison by country/region.

    Values are percentages.
    """
    return _get_payload(include_2050_targets, include_solar_share)


@router.get("/international-renewable-comparison/export")
async def export_international_renewable_comparison(
    include_2050_targets: bool = Query(default=True),
    include_solar_share: bool = Query(default=True),
):
    """Excel export for international renewable comparison data."""
    try:
        payload = _get_payload(include_2050_targets, include_solar_share)
        contents = Delivery4ForecastsService.to_excel_diagram2(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=424, detail=f"Export failed: {exc}") from exc

    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=international_renewable_comparison.xlsx"},
    )
