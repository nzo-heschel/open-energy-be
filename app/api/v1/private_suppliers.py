import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.services.private_suppliers_service import PrivateSuppliersService, DEFAULT_CSV_PATH

router = APIRouter(prefix="/private-supplier-connected-consumers", tags=["Private Suppliers' Consumers"])


@router.get("/")
async def get_private_suppliers(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Monthly time series of private supplier connected consumers with optional segment breakdowns.
    """
    try:
        return PrivateSuppliersService.get_data(start_date, end_date)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load private suppliers data: {exc}")


@router.get("/export")
async def export_private_suppliers(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Export filtered/segmented result to Excel.
    """
    try:
        payload = PrivateSuppliersService.get_data(start_date, end_date)
        contents = PrivateSuppliersService.to_excel(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to export data: {exc}")

    filename = "private_suppliers_consumers.xlsx"
    return StreamingResponse(
        iter([contents]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/download-source")
async def download_source_file():
    """
    Pass-through download of the current master CSV file.
    """
    csv_path = DEFAULT_CSV_PATH
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Source file not found.")
    return FileResponse(
        path=csv_path,
        filename=csv_path.name,
        media_type="text/csv",
    )
