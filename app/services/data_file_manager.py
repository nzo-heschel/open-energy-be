import os
import re
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
    # Private suppliers now uses the _tzarchan source file.
    DataFileSource.PRIVATE_SUPPLIERS.value: "Files_Netunei_hashmal_mp_tzarchan",
    # Switching requests now uses the _niyud source file.
    DataFileSource.SWITCHING_REQUESTS.value: "Files_Netunei_hashmal_mp_niyud",
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


def _age_days(path: Path) -> float:
    """
    Prefer the dd-mm-YYYY suffix in the filename for age; fall back to mtime.
    """
    match = re.search(r"_(\d{2}-\d{2}-\d{4})", path.stem)
    if match:
        try:
            date_part = datetime.strptime(match.group(1), "%d-%m-%Y")
            return (datetime.now() - date_part).total_seconds() / 86400
        except ValueError:
            pass
    return (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 86400


def ensure_fresh_data_file(
    dataset: Union[str, DataFileSource],
    allow_stale: bool = False,
) -> Path:
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

    age_days = _age_days(path)
    if age_days > MAX_AGE_DAYS:
        if allow_stale:
            return path
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
    # Stream the file to disk in chunks to avoid high memory usage.
    chunk_size = 1024 * 1024  # 1MB
    with open(dest, "wb") as buffer:
        while chunk := await upload.read(chunk_size):
            buffer.write(chunk)
    return dest


def data_file_status(dataset: Union[str, DataFileSource]) -> dict:
    path = _latest_file(dataset)
    if not path:
        return {"dataset": _normalize_dataset(dataset), "status": "missing"}
    age_days = _age_days(path)
    return {
        "dataset": _normalize_dataset(dataset),
        "status": "fresh" if age_days <= MAX_AGE_DAYS else "stale",
        "age_days": age_days,
        "filename": path.name,
    }
