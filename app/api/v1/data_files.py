from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.utils.enums import DataFileSource
from app.services.data_file_manager import data_file_status, save_uploaded_data_file

router = APIRouter(prefix="/data-files", tags=["Data Files"])


@router.get("/status")
async def get_data_file_status():
    """
    Returns freshness status for both datasets (private_suppliers and switching_requests).
    """
    return {
        source.value: data_file_status(source)
        for source in DataFileSource
    }


@router.post("/upload")
async def upload_data_file(
    source: DataFileSource = Form(..., description="Data source: private_suppliers or switching_requests"),
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
