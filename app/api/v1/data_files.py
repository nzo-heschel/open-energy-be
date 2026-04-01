from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from app.utils.enums import DataFileSource
from app.services.data_file_manager import data_file_status, save_uploaded_data_file
from app.services.csv_downloader_service import (
    download_csv,
    download_all,
    SOURCE_URLS,
    DOWNLOADABLE_SOURCES,
)

router = APIRouter(prefix="/data-files", tags=["Data Files"])


# ── Existing endpoints ───────────────────────────────────────────────────

@router.get("/status")
async def get_data_file_status():
    """
    Returns freshness status for all datasets.
    """
    return {
        source.value: data_file_status(source)
        for source in DataFileSource
    }


@router.post("/upload")
async def upload_data_file(
    source: DataFileSource = Form(
        ...,
        description=(
            "Data source: private_suppliers (Files_Netunei_hashmal_mp_tzarchan) "
            "or switching_requests (Files_Netunei_hashmal_mp_niyud)"
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


# ── NEW: Server-side CSV download (zero human intervention) ─────────────

@router.get("/download-urls")
async def list_download_urls():
    """
    List the gov.il download URLs the server can fetch automatically.
    These are the direct links to the Israel Electricity Authority CSV files.
    Since the server runs in Israel (AWS), no Cloudflare captcha is triggered.
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
            "Dataset to download from gov.il. "
            "Options: private_suppliers, switching_requests"
        ),
    ),
):
    """
    **Download a CSV directly from gov.il into the server's data_files/ directory.**

    This replaces the manual workflow of:
    1. Opening the gov.il link in a browser
    2. Downloading the CSV
    3. Uploading it via /upload

    Since the server is deployed on AWS Israel, gov.il does NOT show
    a Cloudflare captcha — the file downloads instantly.

    Uses curl_cffi (Chrome TLS fingerprint) → httpx → requests as fallbacks.
    """
    if source not in DOWNLOADABLE_SOURCES:
        allowed = ", ".join(sorted(DOWNLOADABLE_SOURCES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source '{source}'. Allowed: {allowed}",
        )

    result = await download_csv(source)

    if not result["success"]:
        raise HTTPException(
            status_code=502,
            detail=result,
        )

    return result


@router.post("/fetch-all")
async def fetch_all_data_files():
    """
    **Download ALL available CSVs from gov.il in one call.**

    Downloads both private_suppliers and switching_requests files
    directly into data_files/ on the server. Zero human intervention.

    Returns per-dataset results showing success/failure for each.
    """
    results = await download_all()

    all_ok = all(r["success"] for r in results.values())
    any_ok = any(r["success"] for r in results.values())

    return {
        "overall": "all_success" if all_ok else ("partial_success" if any_ok else "all_failed"),
        "datasets": results,
    }

