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
import csv
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo

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
    # Delivery 3 - IMS weather API for heat-load endpoint.
    DataFileSource.IMS_HEAT_LOAD_WEATHER.value: "https://api.ims.gov.il/v1/envista/stations",
}

# Which datasets this downloader supports.
DOWNLOADABLE_SOURCES = set(SOURCE_URLS.keys())

IMS_COLUMNS = ["תחנה", "תאריך ושעה (שעון עולמי)", "לחות יחסית (%)", "טמפרטורה (C°)"]
IMS_API_BASE_URL = os.getenv("IMS_API_BASE_URL", "https://api.ims.gov.il/v1/envista").rstrip("/")
IMS_STATIONS_URL = f"{IMS_API_BASE_URL}/stations"
IMS_JERUSALEM_TZ = ZoneInfo("Asia/Jerusalem")
IMS_LOOKBACK_DAYS = int(os.getenv("IMS_LOOKBACK_DAYS", "30"))
IMS_REQUEST_TIMEOUT_SECONDS = float(os.getenv("IMS_REQUEST_TIMEOUT_SECONDS", "12"))
IMS_RETRY_ATTEMPTS = int(os.getenv("IMS_RETRY_ATTEMPTS", "2"))
IMS_MIN_SPLIT_RANGE_DAYS = int(os.getenv("IMS_MIN_SPLIT_RANGE_DAYS", "7"))

IMS_TARGET_STATIONS = {
    "tel_aviv_coast": ["tel aviv coast", "תל אביב חוף", "tel-aviv coast"],
    "jerusalem_center": ["jerusalem center", "jerusalem centre", "ירושלים מרכז"],
    "jerusalem_givat_ram": ["jerusalem givat ram", "ירושלים גבעת רם", "givat ram"],
}

IMS_STATION_OUTPUT = {
    "tel_aviv_coast": "תל-אביב, חוף",
    "jerusalem_center": "ירושלים, מרכז",
    "jerusalem_givat_ram": "ירושלים, גבעת רם",
}


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
    Check if downloaded content is a valid CSV/XLSX, not an HTML error page.
    Returns an error string if invalid, None if OK.

    XLSX files start with the ZIP magic ``PK\\x03\\x04``; CSV files start with
    text (possibly a BOM) but never an HTML tag. If the first non-whitespace
    characters look like HTML, gov.il is returning a 403/captcha/error page,
    not the CSV. Saving that would clobber the last good file on disk.
    """
    head = content[:4]
    if head.startswith(b"PK\x03\x04"):
        return None  # Looks like a valid XLSX
    snippet = content[:2000].decode("utf-8", errors="ignore")
    stripped = snippet.lstrip().lower()
    if stripped.startswith(("<!doctype html", "<html", "<?xml", "<head", "<body")):
        return (
            "Downloaded content is an HTML page (likely 403/captcha from gov.il), "
            "not the actual CSV. Keeping the previously stored file."
        )
    if "<html" in stripped and ("captcha" in stripped or "challenge" in stripped):
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

def _normalize_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _extract_station_id(station: Dict[str, Any]) -> Optional[int]:
    for key in ("stationId", "station_id", "id"):
        value = station.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _station_name(station: Dict[str, Any]) -> str:
    return str(station.get("name") or station.get("shortName") or station.get("stationTarget") or "")


def _is_active_station(station: Dict[str, Any]) -> bool:
    active = station.get("active")
    return True if active is None else bool(active)


def _pick_ims_channel_id(station: Dict[str, Any], metric_code: str) -> Optional[int]:
    monitors = station.get("monitors") or []
    if not isinstance(monitors, list):
        return None

    metric = metric_code.upper()
    preferred: Optional[int] = None
    for monitor in monitors:
        if not isinstance(monitor, dict):
            continue
        channel_id = monitor.get("channelId")
        if channel_id is None:
            continue
        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            continue
        name = _normalize_name(str(monitor.get("name") or ""))
        alias = _normalize_name(str(monitor.get("alias") or ""))
        units = _normalize_name(str(monitor.get("units") or ""))
        is_active = bool(monitor.get("active", True))

        if metric == "TD":
            is_match = (
                name.startswith("td")
                or alias.startswith("td")
                or "temperature" in name
                or "temperature" in alias
                or "degc" in units
            )
        else:
            is_match = (
                name.startswith("rh")
                or alias.startswith("rh")
                or "humidity" in name
                or "humidity" in alias
                or units == "%"
            )
        if not is_match:
            continue
        if is_active:
            return channel_id
        if preferred is None:
            preferred = channel_id
    return preferred


def _resolve_ims_station_config(stations: list[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    normalized_targets = {
        key: [_normalize_name(alias) for alias in aliases]
        for key, aliases in IMS_TARGET_STATIONS.items()
    }

    matches: Dict[str, Dict[str, int]] = {}
    for target_key, aliases in normalized_targets.items():
        active_candidate: Optional[Dict[str, Any]] = None
        inactive_candidate: Optional[Dict[str, Any]] = None

        for station in stations:
            if not isinstance(station, dict):
                continue
            station_id = _extract_station_id(station)
            if station_id is None:
                continue
            normalized_station_name = _normalize_name(_station_name(station))
            if not normalized_station_name:
                continue
            if not any(alias in normalized_station_name for alias in aliases):
                continue
            if _is_active_station(station):
                active_candidate = station
                break
            if inactive_candidate is None:
                inactive_candidate = station

        selected = active_candidate or inactive_candidate
        if not selected:
            continue

        station_id = _extract_station_id(selected)
        if station_id is None:
            continue
        td_channel = _pick_ims_channel_id(selected, "TD")
        rh_channel = _pick_ims_channel_id(selected, "RH")
        if td_channel is None or rh_channel is None:
            continue
        matches[target_key] = {
            "station_id": station_id,
            "td_channel": td_channel,
            "rh_channel": rh_channel,
        }
    return matches


def _parse_ims_datetime_to_utc(raw_value: Any) -> Optional[datetime]:
    if raw_value is None:
        return None
    raw_text = str(raw_value).strip()
    if not raw_text:
        return None

    candidate = raw_text.replace("Z", "+00:00")
    dt: Optional[datetime] = None
    for fmt in (
        None,
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%d/%m/%Y %H:%M",
    ):
        try:
            if fmt is None:
                dt = datetime.fromisoformat(candidate)
            else:
                dt = datetime.strptime(candidate, fmt)
            break
        except ValueError:
            continue
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IMS_JERUSALEM_TZ)
    return dt.astimezone(timezone.utc)


def _extract_metric_value(entry: Dict[str, Any], metric_code: str) -> Optional[float]:
    channels = entry.get("channels")
    metric = metric_code.upper()

    if isinstance(channels, list):
        for channel in channels:
            if not isinstance(channel, dict):
                continue
            status = channel.get("status")
            valid = channel.get("valid")
            if valid is False:
                continue
            if status not in (None, 1, "1"):
                continue
            name = _normalize_name(str(channel.get("name") or ""))
            alias = _normalize_name(str(channel.get("alias") or ""))
            if metric == "TD":
                matches = name.startswith("td") or alias.startswith("td") or "temperature" in name
            else:
                matches = name.startswith("rh") or alias.startswith("rh") or "humidity" in name
            if not matches:
                continue
            try:
                return float(channel.get("value"))
            except (TypeError, ValueError):
                continue

    if "value" in entry:
        try:
            return float(entry.get("value"))
        except (TypeError, ValueError):
            return None

    return None


def _decode_response_snippet(content: bytes, limit: int = 160) -> str:
    text = content[:limit].decode("utf-8", errors="ignore").replace("\n", " ").replace("\r", " ")
    return " ".join(text.split())


def _parse_ims_response_json(resp: Any, *, context: str) -> Any:
    content_type = (resp.headers.get("content-type") or "").lower()
    if "json" not in content_type:
        raise ValueError(
            f"{context} returned non-JSON content-type '{content_type or 'unknown'}': "
            f"{_decode_response_snippet(resp.content)}"
        )

    try:
        return resp.json()
    except ValueError as exc:
        raise ValueError(
            f"{context} returned invalid JSON: {_decode_response_snippet(resp.content)}"
        ) from exc


def _fetch_ims_station_metric(
    *,
    token: str,
    station_id: int,
    channel_id: int,
    metric_code: str,
    from_date: datetime,
    to_date: datetime,
) -> Dict[datetime, float]:
    import requests

    headers = {"Authorization": f"ApiToken {token}"}
    def _fetch_range(range_start: datetime, range_end: datetime) -> Dict[datetime, float]:
        from_str = range_start.strftime("%Y/%m/%d")
        to_str = range_end.strftime("%Y/%m/%d")
        url = f"{IMS_STATIONS_URL}/{station_id}/data/{channel_id}?from={from_str}&to={to_str}"
        context = f"IMS station {station_id} channel {channel_id} ({metric_code}) {from_str}->{to_str}"

        last_error: Optional[Exception] = None
        for _ in range(max(1, IMS_RETRY_ATTEMPTS)):
            try:
                resp = requests.get(url, headers=headers, timeout=IMS_REQUEST_TIMEOUT_SECONDS)
                resp.raise_for_status()
                payload = _parse_ims_response_json(resp, context=context)
                rows = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    return {}

                result: Dict[datetime, float] = {}
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    ts_utc = _parse_ims_datetime_to_utc(row.get("datetime"))
                    if ts_utc is None:
                        continue
                    metric_value = _extract_metric_value(row, metric_code)
                    if metric_value is None:
                        continue
                    result[ts_utc.replace(tzinfo=None)] = metric_value
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        range_days = max(0, (range_end - range_start).days)
        if range_days <= IMS_MIN_SPLIT_RANGE_DAYS:
            logger.warning("Skipping IMS slice after repeated failures: %s", context)
            if last_error:
                logger.warning("Last IMS slice error: %s", last_error)
            return {}

        midpoint = range_start + timedelta(days=range_days // 2)
        left = _fetch_range(range_start, midpoint)
        right_start = midpoint + timedelta(days=1)
        right = _fetch_range(right_start, range_end) if right_start <= range_end else {}
        left.update(right)
        return left

    return _fetch_range(from_date, to_date)


def _build_ims_weather_csv_content() -> tuple[bytes, Dict[str, Any]]:
    return _build_ims_weather_csv_content_for_range()


def _build_ims_weather_csv_content_for_range(
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
) -> tuple[bytes, Dict[str, Any]]:
    import requests

    token = os.getenv("IMS_TOKEN")
    if not token:
        raise ValueError("IMS_TOKEN is not configured.")

    headers = {"Authorization": f"ApiToken {token}"}
    stations_response = requests.get(
        IMS_STATIONS_URL,
        headers=headers,
        timeout=IMS_REQUEST_TIMEOUT_SECONDS,
    )
    stations_response.raise_for_status()
    stations_payload = _parse_ims_response_json(stations_response, context="IMS stations list")
    if not isinstance(stations_payload, list):
        raise ValueError("Unexpected IMS stations response format.")

    station_config = _resolve_ims_station_config(stations_payload)
    missing_station_keys = [key for key in IMS_TARGET_STATIONS if key not in station_config]
    if missing_station_keys:
        missing_labels = [IMS_STATION_OUTPUT.get(key, key) for key in missing_station_keys]
        raise ValueError(
            "Missing IMS station/channel configuration for: " + ", ".join(missing_labels)
        )

    if end_dt is None:
        utc_now = datetime.now(timezone.utc)
        end_dt = datetime(utc_now.year, utc_now.month, utc_now.day)
    else:
        end_dt = datetime(end_dt.year, end_dt.month, end_dt.day)

    if start_dt is None:
        start_dt = end_dt - timedelta(days=max(1, IMS_LOOKBACK_DAYS))
    else:
        start_dt = datetime(start_dt.year, start_dt.month, start_dt.day)

    if start_dt > end_dt:
        raise ValueError("IMS weather range is invalid: start_dt is after end_dt.")

    rows: list[list[str]] = []
    for station_key, config in station_config.items():
        station_id = config["station_id"]
        td_data = _fetch_ims_station_metric(
            token=token,
            station_id=station_id,
            channel_id=config["td_channel"],
            metric_code="TD",
            from_date=start_dt,
            to_date=end_dt,
        )
        rh_data = _fetch_ims_station_metric(
            token=token,
            station_id=station_id,
            channel_id=config["rh_channel"],
            metric_code="RH",
            from_date=start_dt,
            to_date=end_dt,
        )
        common_timestamps = sorted(set(td_data.keys()) & set(rh_data.keys()))
        for ts_utc in common_timestamps:
            rows.append(
                [
                    IMS_STATION_OUTPUT[station_key],
                    ts_utc.strftime("%d/%m/%Y %H:%M"),
                    f"{rh_data[ts_utc]:g}",
                    f"{td_data[ts_utc]:g}",
                ]
            )

    if not rows:
        raise ValueError("IMS API returned no overlapping TD/RH records for the selected stations.")

    rows.sort(key=lambda item: (item[1], item[0]))
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(IMS_COLUMNS)
    writer.writerows(rows)

    csv_bytes = output.getvalue().encode("utf-8-sig")
    meta = {
        "source": IMS_STATIONS_URL,
        "from": start_dt.strftime("%Y-%m-%d"),
        "to": end_dt.strftime("%Y-%m-%d"),
        "stations": {key: cfg["station_id"] for key, cfg in station_config.items()},
        "records": len(rows),
    }
    return csv_bytes, meta


def download_ims_weather_file(
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
) -> tuple[Path, Dict[str, Any]]:
    content, ims_meta = _build_ims_weather_csv_content_for_range(start_dt, end_dt)
    dest = _save_downloaded_file(DataFileSource.IMS_HEAT_LOAD_WEATHER.value, content, "text/csv")
    return dest, ims_meta


def ensure_fresh_ims_weather_file(
    start_dt: datetime,
    end_dt: datetime,
) -> Path:
    existing_path = _latest_file(DataFileSource.IMS_HEAT_LOAD_WEATHER.value)
    try:
        dest, _ = download_ims_weather_file(start_dt, end_dt)
        return dest
    except Exception as exc:  # noqa: BLE001
        if existing_path:
            logger.warning(
                "IMS range download failed, using existing weather file %s: %s",
                existing_path.name,
                exc,
            )
            return existing_path
        raise


async def download_csv(
    dataset: str,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
) -> Dict:
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

    if dataset == DataFileSource.IMS_HEAT_LOAD_WEATHER.value:
        try:
            dest, ims_meta = download_ims_weather_file(start_dt, end_dt)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "dataset": dataset,
                "url": url,
                "error": f"Failed to build IMS weather CSV: {exc}",
            }

        return {
            "success": True,
            "dataset": dataset,
            "url": url,
            "stored_as": dest.name,
            "size_bytes": dest.stat().st_size,
            "method": "ims_api",
            "params": {
                "from": ims_meta["from"],
                "to": ims_meta["to"],
                "stations": ims_meta["stations"],
                "required_fields": IMS_COLUMNS,
            },
            "message": "IMS weather CSV downloaded and stored successfully.",
        }

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

    # ── Parse-test before committing to disk ─────────────────────────────
    suffix = ".xlsx" if content_type and ("excel" in content_type.lower() or "spreadsheet" in content_type.lower()) else ".csv"
    if not _is_parseable_bytes(content, suffix):
        return {
            "success": False,
            "dataset": dataset,
            "url": url,
            "error": (
                f"Downloaded {len(content)} bytes but content is not parseable "
                f"as {suffix}. Keeping previously stored file."
            ),
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

    if dataset == DataFileSource.IMS_HEAT_LOAD_WEATHER.value:
        try:
            content, ims_meta = _build_ims_weather_csv_content()
            dest = _save_downloaded_file(dataset, content, "text/csv")
            logger.info(
                "Auto-refresh: %s downloaded -> %s (%s to %s, %s records)",
                dataset,
                dest.name,
                ims_meta["from"],
                ims_meta["to"],
                ims_meta["records"],
            )
            return dest
        except Exception as exc:  # noqa: BLE001
            logger.warning("Auto-refresh download failed for %s: %s", dataset, exc)
            return None

    content, content_type, method_used, error_log = _download_bytes(url, dataset)

    if content is None:
        logger.warning(
            "Auto-refresh download failed for %s: %s",
            dataset,
            "; ".join(error_log) or "unknown error",
        )
        return None

    # Validate it's not a captcha page / HTML error response.
    validation_error = _validate_content(content)
    if validation_error:
        logger.warning("Auto-refresh validation failed for %s: %s", dataset, validation_error)
        return None

    # Parse-test the bytes BEFORE writing to disk. ``_save_downloaded_file``
    # also cleans up older sibling files, so writing a bad file would erase
    # our last-good fallback. Bailing here keeps the previous file intact.
    suffix = ".xlsx" if content_type and ("excel" in content_type.lower() or "spreadsheet" in content_type.lower()) else ".csv"
    if not _is_parseable_bytes(content, suffix):
        logger.warning(
            "Auto-refresh for %s downloaded %d bytes but the content is not "
            "parseable as %s — keeping previous file.",
            dataset, len(content), suffix,
        )
        return None

    # Save (old files cleaned AFTER new file is written).
    dest = _save_downloaded_file(dataset, content, content_type)
    logger.info("Auto-refresh: %s downloaded → %s", dataset, dest.name)
    return dest


def _is_parseable_bytes(content: bytes, suffix: str) -> bool:
    """Sanity-check downloaded bytes look like a real CSV/XLSX with headers.

    Runs on in-memory bytes so we can decide whether to commit to disk —
    we don't want to write a bad file because writing also deletes older
    sibling files (the auto-cleanup in ``_save_downloaded_file``).
    """
    try:
        head = content[:256].lstrip().decode("utf-8", errors="ignore").lower()
        if head.startswith(("<!doctype html", "<html", "<head", "<body", "<?xml")):
            return False

        import pandas as pd
        from io import BytesIO

        if suffix == ".xlsx":
            pd.read_excel(BytesIO(content), nrows=1)
            return True
        for enc in ("utf-8-sig", "utf-8", "cp1255", "cp1252", "iso-8859-8", "latin1"):
            try:
                pd.read_csv(BytesIO(content), encoding=enc, nrows=1)
                return True
            except Exception:
                continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("Parseability check on downloaded bytes failed: %s", exc)
    return False


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
        # Download + parse-test both succeeded inside _try_download_sync.
        return new_path

    # Download failed (or the downloaded bytes were unparseable / HTML). The
    # previous file is still intact because we parse-test BEFORE writing to
    # disk — fall back to it silently so the endpoint keeps serving.
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
