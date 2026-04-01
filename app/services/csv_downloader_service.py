# app/services/csv_downloader_service.py
"""
Server-side CSV downloader for Israel Electricity Authority data files.

Since the backend is deployed on AWS Israel, requests to gov.il do NOT
trigger Cloudflare captcha (only happens from Pakistan / certain regions).
This service downloads the CSV files directly into the data_files directory,
eliminating the need for manual download + upload.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.services.data_file_manager import DATA_FILES_DIR, DATASET_BASE_NAMES
from app.utils.enums import DataFileSource

logger = logging.getLogger(__name__)

# ── Source URLs (Israel Electricity Authority BI portal) ──────────────────
SOURCE_URLS: Dict[str, str] = {
    DataFileSource.PRIVATE_SUPPLIERS.value: (
        "https://www.gov.il/BlobFolder/generalpage/"
        "bi_olam_haspaka/he/Files_Netunei_hashmal_mp_tzarchan.csv"
    ),
    DataFileSource.SWITCHING_REQUESTS.value: (
        "https://www.gov.il/BlobFolder/generalpage/"
        "bi_olam_haspaka/he/Files_Netunei_hashmal_mp_niyud.csv"
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


def _cleanup_old_files(dataset: str) -> None:
    """Remove older files for this dataset to keep only the latest download."""
    base = DATASET_BASE_NAMES[dataset]
    for pattern in (f"{base}_*", f"{base}.*"):
        for existing in DATA_FILES_DIR.glob(pattern):
            try:
                existing.unlink()
                logger.info("Removed old file: %s", existing.name)
            except OSError:
                continue


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
    DATA_FILES_DIR.mkdir(parents=True, exist_ok=True)

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

    # ── Strategy 2: httpx (async-friendly) ───────────────────────────────
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

    # ── Strategy 3: requests (sync fallback) ─────────────────────────────
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

    # ── No content obtained ──────────────────────────────────────────────
    if content is None:
        return {
            "success": False,
            "dataset": dataset,
            "url": url,
            "error": "All download strategies failed.",
            "details": error_log,
        }

    # ── Sanity-check: reject if the response looks like an HTML captcha page ─
    snippet = content[:2000].decode("utf-8", errors="ignore").lower()
    if "<html" in snippet and ("captcha" in snippet or "challenge" in snippet):
        return {
            "success": False,
            "dataset": dataset,
            "url": url,
            "error": (
                "Downloaded content appears to be a Cloudflare challenge page, "
                "not the actual CSV. The server may need a different IP or proxy."
            ),
            "method": method_used,
        }

    # ── Save to disk ─────────────────────────────────────────────────────
    filename = _dated_filename(dataset, content_type)
    _cleanup_old_files(dataset)

    dest = DATA_FILES_DIR / filename
    dest.write_bytes(content)
    logger.info("Saved %s → %s (%d bytes)", dataset, dest.name, len(content))

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
