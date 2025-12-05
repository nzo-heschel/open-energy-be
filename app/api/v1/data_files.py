from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.data_file_manager import (
    data_file_status,
    save_uploaded_data_file,
)

router = APIRouter(prefix="/data-files", tags=["Data Files"])


@router.get("/status")
async def get_data_file_status():
    """
    Returns freshness status for both datasets (niyud and tzarchan).
    """
    return {
        "niyud": data_file_status("niyud"),
        "tzarchan": data_file_status("tzarchan"),
    }


@router.post("/upload/niyud")
async def upload_data_file_niyud(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided.")
    saved_path = await save_uploaded_data_file("niyud", file)
    return {
        "dataset": "niyud",
        "stored_as": saved_path.name,
        "message": "File uploaded. Re-run the target API to get the updated results.",
    }


@router.post("/upload/tzarchan")
async def upload_data_file_tzarchan(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided.")
    saved_path = await save_uploaded_data_file("tzarchan", file)
    return {
        "dataset": "tzarchan",
        "stored_as": saved_path.name,
        "message": "File uploaded. Re-run the target API to get the updated results.",
    }
