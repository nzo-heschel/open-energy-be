import asyncio
import logging
import os
from typing import Dict, Optional, Tuple

from app.services.data_file_manager import MAX_AGE_DAYS, data_file_status
from app.utils.emailer import send_email_smtp
from app.utils.enums import DataFileSource

logger = logging.getLogger(__name__)
_notified_files: set[Tuple[str, str]] = set()
NOTIFY_THRESHOLD_DAYS = float(os.getenv("DATA_FILES_NOTIFY_THRESHOLD_DAYS", "1"))
_notify_after_minutes = os.getenv("DATA_FILES_NOTIFY_AFTER_MINUTES")
_notify_after_days_env = os.getenv("DATA_FILES_NOTIFY_AFTER_DAYS")
NOTIFY_AFTER_DAYS: Optional[float] = None
if _notify_after_days_env is not None:
    try:
        NOTIFY_AFTER_DAYS = float(_notify_after_days_env)
    except ValueError:
        NOTIFY_AFTER_DAYS = None
elif _notify_after_minutes is not None:
    try:
        NOTIFY_AFTER_DAYS = float(_notify_after_minutes) / 1440.0
    except ValueError:
        NOTIFY_AFTER_DAYS = None

POLL_INTERVAL_SECONDS = float(os.getenv("DATA_FILES_NOTIFIER_INTERVAL_SECONDS", "86400"))


def _smtp_settings() -> Optional[Dict]:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_SENDER", username or "")
    recipients = [addr.strip() for addr in os.getenv("SMTP_RECIPIENTS", "").split(",") if addr.strip()]
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

    if not host or not sender or not recipients:
        logger.info(
            "SMTP settings incomplete; skipping expiry notifications. "
            "Set SMTP_HOST, SMTP_SENDER, SMTP_RECIPIENTS (comma-separated), optional SMTP_USERNAME/SMTP_PASSWORD."
        )
        return None
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "recipients": recipients,
        "use_tls": use_tls,
    }


async def _notify_if_expiring(settings: Dict) -> None:
    for source in DataFileSource:
        status = data_file_status(source)
        filename = status.get("filename")
        age_days = status.get("age_days")
        if filename is None or age_days is None:
            continue
        remaining = MAX_AGE_DAYS - age_days

        if NOTIFY_AFTER_DAYS is not None:
            # Notify when file age crosses configured threshold.
            if age_days < NOTIFY_AFTER_DAYS:
                continue
        else:
            # Default: notify when remaining age is within threshold.
            if remaining > NOTIFY_THRESHOLD_DAYS:
                continue
        key = (source.value, filename)
        if key in _notified_files:
            continue

        subject = f"Data file nearing expiry: {source.value}"
        body = (
            f"The data file '{filename}' for source '{source.value}' is {age_days} days old and will expire "
            f"in {max(remaining, 0)} day(s). Please upload a fresh CSV before it expires."
        )
        try:
            await asyncio.to_thread(
                send_email_smtp,
                settings["host"],
                settings["port"],
                settings["username"],
                settings["password"],
                settings["use_tls"],
                settings["sender"],
                settings["recipients"],
                subject,
                body,
            )
            _notified_files.add(key)
            logger.info("Sent expiry notification for %s (%s)", source.value, filename)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to send expiry notification for %s: %s", source.value, exc)


async def run_file_expiry_notifier(poll_interval_seconds: Optional[float] = None) -> None:
    """
    Periodically check for near-expiry data files and send notification emails.
    Default interval: 24 hours (override via DATA_FILES_NOTIFIER_INTERVAL_SECONDS).
    Optionally notify after a specific file age via DATA_FILES_NOTIFY_AFTER_MINUTES or DATA_FILES_NOTIFY_AFTER_DAYS.
    """
    settings = _smtp_settings()
    if not settings:
        return
    interval = poll_interval_seconds or POLL_INTERVAL_SECONDS
    # Run an immediate check on startup
    await _notify_if_expiring(settings)
    while True:
        try:
            await _notify_if_expiring(settings)
        except Exception as exc:  # noqa: BLE001
            logger.exception("File expiry notifier encountered an error: %s", exc)
        await asyncio.sleep(interval)
