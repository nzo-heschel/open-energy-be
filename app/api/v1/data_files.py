from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.csv_downloader_service import (
    DOWNLOADABLE_SOURCES,
    SOURCE_URLS,
    download_all,
    download_csv,
)
from app.services.data_file_manager import data_file_status, save_uploaded_data_file
from app.utils.date_utils import parse_date
from app.utils.enums import DataFileSource

router = APIRouter(prefix="/data-files", tags=["Data Files"])


@router.get("/status")
async def get_data_file_status():
    """
    Returns freshness status for all datasets.
    """
    return {source.value: data_file_status(source) for source in DataFileSource}


@router.post("/upload")
async def upload_data_file(
    source: DataFileSource = Form(
        ...,
        description=(
            "Data source enum. Includes Electricity Authority datasets and "
            "ims_heat_load_weather for the heat-load weather CSV."
        ),
    ),
    file: UploadFile = File(...),
):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided.")
    saved_path = await save_uploaded_data_file(source, file)
    return {
        "dataset": source.value,
        "stored_as": saved_path.name,
        "message": "File uploaded. Re-run the target API to get the updated results.",
    }


@router.get("/download-urls")
async def list_download_urls():
    """
    List backend download sources for all auto-fetch datasets.
    """
    return {
        dataset: {
            "url": url,
            "status": data_file_status(dataset),
        }
        for dataset, url in SOURCE_URLS.items()
    }


@router.post("/fetch")
async def fetch_data_file(
    source: str = Form(
        ...,
        description=(
            "Dataset to download. Supports Electricity Authority CSVs and "
            "ims_heat_load_weather via IMS token."
        ),
    ),
    start_date: str | None = Form(default=None),
    end_date: str | None = Form(default=None),
):
    """
    Download a CSV into data_files/.

    Supports Electricity Authority direct CSV download and IMS weather CSV
    generation via IMS_TOKEN.
    """
    if source not in DOWNLOADABLE_SOURCES:
        allowed = ", ".join(sorted(DOWNLOADABLE_SOURCES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source '{source}'. Allowed: {allowed}",
        )

    start_dt = parse_date(start_date) if start_date else None
    end_dt = parse_date(end_date) if end_date else None
    result = await download_csv(source, start_dt=start_dt, end_dt=end_dt)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result)
    return result


@router.post("/fetch-ims-weather")
async def fetch_ims_weather_file(
    start_date: str | None = Form(default=None),
    end_date: str | None = Form(default=None),
):
    """
    Download IMS weather CSV for Heat Load vs Generation using IMS_TOKEN.
    """
    start_dt = parse_date(start_date) if start_date else None
    end_dt = parse_date(end_date) if end_date else None
    result = await download_csv(
        DataFileSource.IMS_HEAT_LOAD_WEATHER.value,
        start_dt=start_dt,
        end_dt=end_dt,
    )
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result)
    return result


@router.post("/fetch-all")
async def fetch_all_data_files():
    """
    Download all configured CSV datasets in one call.
    """
    results = await download_all()
    all_ok = all(r["success"] for r in results.values())
    any_ok = any(r["success"] for r in results.values())

    return {
        "overall": "all_success" if all_ok else ("partial_success" if any_ok else "all_failed"),
        "datasets": results,
    }
