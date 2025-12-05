import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

# Default storage under project/data_files unless overridden.
DATA_FILES_DIR = Path(
    os.getenv(
        "DATA_FILES_DIR",
        Path(__file__).resolve().parents[2] / "data_files",
    )
)
MAX_AGE_DAYS = int(os.getenv("DATA_FILES_MAX_AGE_DAYS", "7"))

DATASET_BASE_NAMES = {
    "niyud": "Files_Netunei_hashmal_mp_niyud",
    "tzarchan": "Files_Netunei_hashmal_mp_tzarchan",
}


def _base_name(dataset: str) -> str:
    if dataset not in DATASET_BASE_NAMES:
        raise HTTPException(status_code=400, detail="Invalid dataset. Use 'niyud' or 'tzarchan'.")
    return DATASET_BASE_NAMES[dataset]


def _latest_file(dataset: str) -> Optional[Path]:
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


def ensure_fresh_data_file(dataset: str) -> Path:
    """
    Return path to the freshest file for the dataset.
    Raise 428 if missing or older than MAX_AGE_DAYS.
    """
    path = _latest_file(dataset)
    if not path:
        raise HTTPException(
            status_code=428,
            detail=(
                f"Data file for '{dataset}' is missing. "
                f"Upload a fresh CSV via /api/v1/data-files/upload?dataset={dataset}, then re-run the API."
            ),
        )

    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    if age > timedelta(days=MAX_AGE_DAYS):
        raise HTTPException(
            status_code=428,
            detail=(
                f"Data file for '{dataset}' is older than {MAX_AGE_DAYS} days. "
                f"Upload a fresh CSV via /api/v1/data-files/upload?dataset={dataset}, then re-run the API."
            ),
        )
    return path


async def save_uploaded_data_file(dataset: str, upload: UploadFile) -> Path:
    """
    Save an uploaded file for the dataset, renaming with today's date suffix.
    """
    base = _base_name(dataset)
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


def data_file_status(dataset: str) -> dict:
    path = _latest_file(dataset)
    if not path:
        return {"dataset": dataset, "status": "missing"}
    age_days = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days
    return {
        "dataset": dataset,
        "status": "fresh" if age_days <= MAX_AGE_DAYS else "stale",
        "age_days": age_days,
        "filename": path.name,
    }
