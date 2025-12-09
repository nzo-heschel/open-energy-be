import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

from fastapi import HTTPException, UploadFile

from app.utils.enums import DataFileSource

# Default storage under project/data_files unless overridden.
DATA_FILES_DIR = Path(
    os.getenv(
        "DATA_FILES_DIR",
        Path(__file__).resolve().parents[2] / "data_files",
    )
)
MAX_AGE_DAYS = float(os.getenv("DATA_FILES_MAX_AGE_DAYS", "7"))

DATASET_BASE_NAMES = {
    DataFileSource.PRIVATE_SUPPLIERS.value: "Files_Netunei_hashmal_mp_niyud",
    DataFileSource.SWITCHING_REQUESTS.value: "Files_Netunei_hashmal_mp_tzarchan",
}


def _normalize_dataset(dataset: Union[str, DataFileSource]) -> str:
    return dataset.value if isinstance(dataset, DataFileSource) else dataset


def _base_name(dataset: Union[str, DataFileSource]) -> str:
    normalized = _normalize_dataset(dataset)
    if normalized not in DATASET_BASE_NAMES:
        allowed = ", ".join(source.value for source in DataFileSource)
        raise HTTPException(status_code=400, detail=f"Invalid dataset. Use one of: {allowed}.")
    return DATASET_BASE_NAMES[normalized]


def _latest_file(dataset: Union[str, DataFileSource]) -> Optional[Path]:
    base = _base_name(dataset)
    patterns = [
        f"{base}_*.*",  # preferred dated filename
        f"{base}.*",    # fallback without date
        base,           # fallback without extension
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(DATA_FILES_DIR.glob(pattern))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def ensure_fresh_data_file(dataset: Union[str, DataFileSource]) -> Path:
    """
    Return path to the freshest file for the dataset.
    Raise 428 if missing or older than MAX_AGE_DAYS.
    """
    dataset_key = _normalize_dataset(dataset)
    path = _latest_file(dataset_key)
    if not path:
        raise HTTPException(
            status_code=428,
            detail=(
                f"Data file for '{dataset_key}' is missing. "
                f"Upload a fresh CSV via /api/v1/data-files/upload with source '{dataset_key}' in the request body, then re-run the API."
            ),
        )

    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    if age > timedelta(days=MAX_AGE_DAYS):
        raise HTTPException(
            status_code=428,
            detail=(
                f"Data file for '{dataset_key}' is older than {MAX_AGE_DAYS} days. "
                f"Upload a fresh CSV via /api/v1/data-files/upload with source '{dataset_key}' in the request body, then re-run the API."
            ),
        )
    return path


async def save_uploaded_data_file(dataset: Union[str, DataFileSource], upload: UploadFile) -> Path:
    """
    Save an uploaded file for the dataset, renaming with today's date suffix.
    """
    base = _base_name(dataset)
    dataset_key = _normalize_dataset(dataset)
    incoming_name = (upload.filename or "").lower()
    # If the uploaded filename clearly belongs to a different dataset, reject it.
    other_bases = [
        DATASET_BASE_NAMES[key].lower()
        for key in DATASET_BASE_NAMES
        if key != dataset_key
    ]
    if any(other in incoming_name for other in other_bases):
        allowed = ", ".join(DATASET_BASE_NAMES.keys())
        raise HTTPException(
            status_code=400,
            detail=(
                f"Uploaded file does not match selected source '{dataset_key}'. "
                f"Expected a file for: {dataset_key}. Allowed sources: {allowed}."
            ),
        )

    suffix = Path(upload.filename or "").suffix or ".csv"
    dated_name = f"{base}_{datetime.now().strftime('%d-%m-%Y')}{suffix}"
    DATA_FILES_DIR.mkdir(parents=True, exist_ok=True)

    # Remove older files for this dataset to keep only the latest upload.
    for existing in DATA_FILES_DIR.glob(f"{base}_*"):
        try:
            existing.unlink()
        except OSError:
            continue
    for existing in DATA_FILES_DIR.glob(f"{base}.*"):
        try:
            existing.unlink()
        except OSError:
            continue

    dest = DATA_FILES_DIR / dated_name
    content = await upload.read()
    dest.write_bytes(content)
    return dest


def data_file_status(dataset: Union[str, DataFileSource]) -> dict:
    path = _latest_file(dataset)
    if not path:
        return {"dataset": _normalize_dataset(dataset), "status": "missing"}
    age_days = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 86400
    return {
        "dataset": _normalize_dataset(dataset),
        "status": "fresh" if age_days <= MAX_AGE_DAYS else "stale",
        "age_days": age_days,
        "filename": path.name,
    }
