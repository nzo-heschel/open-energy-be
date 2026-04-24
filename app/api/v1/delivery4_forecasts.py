# app/api/v1/delivery4_forecasts.py
"""
Delivery 4 — Diagram 1 and Diagram 2 forecast endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.delivery4_forecasts_service import Delivery4ForecastsService

# Paths are mounted in main.py (no router prefix here) so Delivery 4 can share the
# renewable namespace while keeping backwards-compatible aliases.
router = APIRouter(tags=["Delivery 4 — Forecasts"])


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
            detail=f"Failed to load Delivery 4 diagram 2: {exc}",
        ) from exc


@router.get("/renewable-forecast-israel")
async def get_renewable_forecast_israel():
    """
    **Delivery 4 — Diagram 1** — Israel renewable trajectory and targets.

    - Data file: `data_files/diagram_sheet_1.csv` (override with `DELIVERY4_DIAGRAM1_CSV_PATH`).
    - Values are **fractions 0–1** (not percent points).
    """
    try:
        return Delivery4ForecastsService.get_israel_forecast()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail=f"Failed to load Delivery 4 diagram 1: {exc}",
        ) from exc


@router.get("/renewable-forecast-israel/export")
async def export_renewable_forecast_israel():
    """Excel export for Diagram 1: data, labels, and metadata."""
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
        headers={
            "Content-Disposition": "attachment; filename=delivery4_diagram1_renewable_forecast_israel.xlsx"
        },
    )


@router.get("/international-renewable-comparison")
async def get_international_renewable_comparison(
    include_2050_targets: bool = Query(
        default=True,
        description="Include 2050 renewable target series (PRD toggle). 2030 is always included.",
    ),
    include_solar_share: bool = Query(
        default=True,
        description="Include 2024 solar share series (PRD toggle).",
    ),
):
    """
    **Delivery 4 — Diagram 2** — horizontal comparison by country/region.

    - Data file: `data_files/diagram_sheet_2.csv` (override with `DELIVERY4_DIAGRAM2_CSV_PATH`).
    - Values are **fractions 0–1** (not percent points).
    - `regions_without_solar_data` lists areas with no published solar figure.
    - `validation` flags unusual rows (e.g. solar share above 2030 renewable target).
    """
    return _get_payload(include_2050_targets, include_solar_share)


@router.get("/international-renewable-comparison/export")
async def export_international_renewable_comparison(
    include_2050_targets: bool = Query(default=True),
    include_solar_share: bool = Query(default=True),
):
    """Excel export: data sheet, meta (titles, filters, source note), and optional “No solar data” list."""
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
        headers={
            "Content-Disposition": "attachment; filename=delivery4_diagram2_international_renewable_comparison.xlsx"
        },
    )
