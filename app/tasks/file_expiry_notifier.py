import asyncio
import logging
import os
from typing import Dict, Optional, Tuple

from app.services.data_file_manager import MAX_AGE_DAYS, data_file_status
from app.utils.enums import DataFileSource

logger = logging.getLogger(__name__)

# SMTP notifications are disabled (VPN / no outbound mail). No-op placeholders retained for reference.
def _smtp_settings() -> Optional[Dict]:
    return None


async def _notify_if_expiring(settings: Dict) -> None:
    return None


async def run_file_expiry_notifier(poll_interval_seconds: Optional[float] = None) -> None:
    """
    Disabled SMTP notifier.
    """
    return None
