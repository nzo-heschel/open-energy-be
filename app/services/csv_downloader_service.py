# app/services/csv_downloader_service.py
"""
Server-side CSV downloader for Israel Electricity Authority data files.

Since the backend is deployed on AWS Israel, requests to gov.il do NOT
trigger Cloudflare captcha (only happens from Pakistan / certain regions).
This service downloads the CSV files directly into the data_files directory,
eliminating the need for manual download + upload.
"""
from __future__ import annotations

import calendar
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

from app.services.data_file_manager import (
    DATA_FILES_DIR,
    DATASET_BASE_NAMES,
    _age_days,
    _latest_file,
    _normalize_dataset,
)
from app.utils.enums import DataFileSource

logger = logging.getLogger(__name__)

# ── Source URLs (Israel Electricity Authority BI portal) ──────────────────
SOURCE_URLS: Dict[str, str] = {
    # Delivery 1 – Private supply world
    DataFileSource.PRIVATE_SUPPLIERS.value: (
        "https://www.gov.il/BlobFolder/generalpage/"
        "bi_olam_haspaka/he/Files_Netunei_hashmal_mp_tzarchan.csv"
    ),
    DataFileSource.SWITCHING_REQUESTS.value: (
        "https://www.gov.il/BlobFolder/generalpage/"
        "bi_olam_haspaka/he/Files_Netunei_hashmal_mp_niyud.csv"
    ),
    # Delivery 2 – Renewable energy (connected facilities & distributor responses)
    DataFileSource.CONNECTED_FACILITIES.value: (
        "https://www.gov.il/BlobFolder/generalpage/"
        "bipua2024/he/Files_Netunei_hashmal_my_mehubarim.csv"
    ),
    DataFileSource.DISTRIBUTOR_RESPONSES.value: (
        "https://www.gov.il/BlobFolder/generalpage/"
        "bipua2024/he/Files_Netunei_hashmal_my_teshuvotmehalek.csv"
    ),
}

# Which datasets this downloader supports.
DOWNLOADABLE_SOURCES = set(SOURCE_URLS.keys())


def _dated_filename(dataset: str, content_type: Optional[str] = None) -> str:
    """Build a filename like  Files_Netunei_hashmal_mp_tzarchan_01-04-2026.csv"""
    base = DATASET_BASE_NAMES[dataset]
    # Infer extension from Content-Type if available, default to .csv
    ext = ".csv"
    if content_type:
        ct = content_type.lower()
        if "excel" in ct or "spreadsheet" in ct:
            ext = ".xlsx"
    return f"{base}_{datetime.now().strftime('%d-%m-%Y')}{ext}"


def _cleanup_old_files(dataset: str, exclude: Optional[Path] = None) -> None:
    """
    Remove older files for this dataset to keep only the latest download.
    Optionally exclude a specific path from deletion (the file we just saved).
    """
    base = DATASET_BASE_NAMES[dataset]
    for pattern in (f"{base}_*", f"{base}.*"):
        for existing in DATA_FILES_DIR.glob(pattern):
            if exclude and existing.resolve() == exclude.resolve():
                continue
            try:
                existing.unlink()
                logger.info("Removed old file: %s", existing.name)
            except OSError:
                continue


def _download_bytes(url: str, dataset: str) -> tuple[Optional[bytes], Optional[str], Optional[str], list[str]]:
    """
    Core download logic shared by all callers.
    Returns (content, content_type, method_used, error_log).
    This is synchronous-safe: curl_cffi and requests are sync,
    httpx is skipped here (see _download_bytes_async for async variant).
    """
    content: Optional[bytes] = None
    content_type: Optional[str] = None
    method_used: Optional[str] = None
    error_log: list[str] = []

    # ── Strategy 1: curl_cffi (best for Cloudflare) ──────────────────────
    try:
        from curl_cffi import requests as cffi_requests

        resp = cffi_requests.get(
            url,
            impersonate="chrome",
            timeout=120,
            allow_redirects=True,
        )
        if resp.status_code == 200 and len(resp.content) > 500:
            content = resp.content
            content_type = resp.headers.get("content-type", "")
            method_used = "curl_cffi"
            logger.info("Downloaded %s via curl_cffi (%d bytes)", dataset, len(content))
        else:
            msg = f"curl_cffi: status={resp.status_code}, body_len={len(resp.content)}"
            error_log.append(msg)
            logger.warning(msg)
    except Exception as exc:
        msg = f"curl_cffi failed: {exc}"
        error_log.append(msg)
        logger.warning(msg)

    # ── Strategy 2: requests (sync fallback) ─────────────────────────────
    if content is None:
        try:
            import requests

            resp = requests.get(url, timeout=120, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 500:
                content = resp.content
                content_type = resp.headers.get("content-type", "")
                method_used = "requests"
                logger.info("Downloaded %s via requests (%d bytes)", dataset, len(content))
            else:
                msg = f"requests: status={resp.status_code}, body_len={len(resp.content)}"
                error_log.append(msg)
                logger.warning(msg)
        except Exception as exc:
            msg = f"requests failed: {exc}"
            error_log.append(msg)
            logger.warning(msg)

    return content, content_type, method_used, error_log


def _validate_content(content: bytes) -> Optional[str]:
    """
    Check if downloaded content is a valid CSV, not a captcha page.
    Returns an error string if invalid, None if OK.
    """
    snippet = content[:2000].decode("utf-8", errors="ignore").lower()
    if "<html" in snippet and ("captcha" in snippet or "challenge" in snippet):
        return (
            "Downloaded content appears to be a Cloudflare challenge page, "
            "not the actual CSV. The server may need a different IP or proxy."
        )
    return None


def _save_downloaded_file(dataset: str, content: bytes, content_type: Optional[str]) -> Path:
    """
    Save downloaded bytes to a dated file in data_files/.
    Cleans up old files for this dataset AFTER the new file is saved.
    """
    DATA_FILES_DIR.mkdir(parents=True, exist_ok=True)
    filename = _dated_filename(dataset, content_type)
    dest = DATA_FILES_DIR / filename
    dest.write_bytes(content)
    logger.info("Saved %s → %s (%d bytes)", dataset, dest.name, len(content))

    # Only now clean up old files, excluding the one we just saved.
    _cleanup_old_files(dataset, exclude=dest)

    return dest


# ─────────────────────────────────────────────────────────────────────────
# Public API: used by /data-files/fetch and /data-files/fetch-all
# ─────────────────────────────────────────────────────────────────────────

async def download_csv(dataset: str) -> Dict:
    """
    Download the CSV for *dataset* from gov.il and save it to data_files/.

    Returns a dict with status information.

    Strategy:
      1. Try curl_cffi (best Cloudflare bypass, impersonates Chrome).
      2. Fallback to httpx (lightweight async HTTP).
      3. Fallback to requests (sync, simple).
    """
    if dataset not in SOURCE_URLS:
        allowed = ", ".join(sorted(DOWNLOADABLE_SOURCES))
        return {
            "success": False,
            "dataset": dataset,
            "error": f"No download URL configured for '{dataset}'. Downloadable: {allowed}",
        }

    url = SOURCE_URLS[dataset]

    # Use the core sync downloader first
    content, content_type, method_used, error_log = _download_bytes(url, dataset)

    # ── Async httpx attempt if sync methods failed ───────────────────────
    if content is None:
        try:
            import httpx

            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(120.0),
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.content) > 500:
                    content = resp.content
                    content_type = resp.headers.get("content-type", "")
                    method_used = "httpx"
                    logger.info("Downloaded %s via httpx (%d bytes)", dataset, len(content))
                else:
                    msg = f"httpx: status={resp.status_code}, body_len={len(resp.content)}"
                    error_log.append(msg)
                    logger.warning(msg)
        except Exception as exc:
            msg = f"httpx failed: {exc}"
            error_log.append(msg)
            logger.warning(msg)

    # ── No content obtained ──────────────────────────────────────────────
    if content is None:
        return {
            "success": False,
            "dataset": dataset,
            "url": url,
            "error": "All download strategies failed.",
            "details": error_log,
        }

    # ── Sanity-check ─────────────────────────────────────────────────────
    validation_error = _validate_content(content)
    if validation_error:
        return {
            "success": False,
            "dataset": dataset,
            "url": url,
            "error": validation_error,
            "method": method_used,
        }

    # ── Save to disk (old files cleaned AFTER successful save) ───────────
    dest = _save_downloaded_file(dataset, content, content_type)

    return {
        "success": True,
        "dataset": dataset,
        "url": url,
        "stored_as": dest.name,
        "size_bytes": len(content),
        "method": method_used,
        "message": (
            f"File downloaded and saved successfully. "
            f"Re-run the target API to get updated results."
        ),
    }


async def download_all() -> Dict[str, Dict]:
    """Download all supported datasets. Returns per-dataset results."""
    results: Dict[str, Dict] = {}
    for dataset in DOWNLOADABLE_SOURCES:
        results[dataset] = await download_csv(dataset)
    return results


# ─────────────────────────────────────────────────────────────────────────
# Auto-refresh: used directly inside endpoint services
# (private_suppliers_service, switching_requests_service)
#
# Priority 1 → Download fresh file and use it.
# Priority 2 → If download fails, silently use the old/stale file.
# NEVER raise an error to the client if any file exists on disk.
# ─────────────────────────────────────────────────────────────────────────

def _days_in_current_month() -> int:
    """Return 28-31 depending on the current month/year."""
    now = datetime.now()
    return calendar.monthrange(now.year, now.month)[1]


def _needs_refresh(dataset: str) -> bool:
    """Return True if the dataset file is missing or older than the current month length."""
    path = _latest_file(dataset)
    if path is None:
        return True
    return _age_days(path) > _days_in_current_month()


def _try_download_sync(dataset: str) -> Optional[Path]:
    """
    Attempt a synchronous download of the dataset CSV from gov.il.
    Returns the saved Path on success, None on failure.
    Does NOT delete old files until the new one is safely on disk.
    """
    if dataset not in SOURCE_URLS:
        return None

    url = SOURCE_URLS[dataset]

    content, content_type, method_used, error_log = _download_bytes(url, dataset)

    if content is None:
        logger.warning(
            "Auto-refresh download failed for %s: %s",
            dataset,
            "; ".join(error_log) or "unknown error",
        )
        return None

    # Validate it's not a captcha page
    validation_error = _validate_content(content)
    if validation_error:
        logger.warning("Auto-refresh validation failed for %s: %s", dataset, validation_error)
        return None

    # Save (old files cleaned AFTER new file is written)
    dest = _save_downloaded_file(dataset, content, content_type)
    logger.info("Auto-refresh: %s downloaded → %s", dataset, dest.name)
    return dest


def ensure_fresh_or_download(dataset: Union[str, DataFileSource]) -> Path:
    """
    Smart data-file resolver for endpoint services.

    1. If a fresh file exists → return it immediately (no download needed).
    2. If file is stale or missing → try downloading a fresh one from gov.il.
       a. If download succeeds → save it, clean old files, return new path.
       b. If download fails and an old file exists → return old file silently.
       c. If download fails and NO file exists → raise ValueError (only then).

    This ensures the client NEVER sees an error as long as any data file
    exists on disk, even if it's old.
    """
    dataset_key = _normalize_dataset(dataset)

    # Check current state
    existing_path = _latest_file(dataset_key)

    monthly_threshold = _days_in_current_month()
    if existing_path and _age_days(existing_path) <= monthly_threshold:
        # File is fresh (within current month window) — no action needed
        return existing_path

    # File is stale or missing — try downloading
    logger.info(
        "Auto-refresh triggered for %s (current: %s)",
        dataset_key,
        existing_path.name if existing_path else "MISSING",
    )

    new_path = _try_download_sync(dataset_key)

    if new_path:
        # Download succeeded — return the new file
        return new_path

    # Download failed — fall back to existing stale file if available
    if existing_path:
        logger.warning(
            "Auto-refresh failed for %s, using stale file: %s",
            dataset_key,
            existing_path.name,
        )
        return existing_path

    # No file at all and download failed — this is the only error case
    raise ValueError(
        f"Data file for '{dataset_key}' is missing and automatic download failed. "
        f"Upload a file manually via /api/v1/data-files/upload or "
        f"trigger /api/v1/data-files/fetch with source='{dataset_key}'."
    )
