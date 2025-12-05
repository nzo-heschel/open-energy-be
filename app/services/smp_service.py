import json
import time
from typing import Dict, List
import httpx

from app.config import configure_global_proxy

BASE_URL = "https://apim-api.noga-iso.co.il/"
_CACHE: Dict[tuple[str, str], Dict] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes to avoid hammering the external API
SMP_PATHS = [
    "TRADING/SMP/v1",           # likely SMP endpoint
    "SMP/SMPAPI/v1",            # alternate naming
    "trade/smp/v1",             # lowercase path variants
    "trading/smp/v1",
]


class SMPService:
    @staticmethod
    async def fetch_smp_data(start: str, end: str, token: str) -> List[Dict]:
        """
        Fetch SMP data from the NOGA API using an async client and short-term caching.
        """
        # Ensure proxies are applied when the module is used directly.
        configure_global_proxy()

        cache_key = (start, end)
        now = time.time()
        cached = _CACHE.get(cache_key)
        if cached and cached["expires_at"] > now:
            return cached["data"]

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Ocp-Apim-Subscription-Key": token,
        }

        last_exc: Exception | None = None
        result = None
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
        async with httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            trust_env=True,  # honor HTTP(S)_PROXY
        ) as client:
            for path in SMP_PATHS:
                try:
                    response = await client.post(path, headers=headers, json={"fromDate": start, "toDate": end})
                    response.raise_for_status()
                    result = response.json()
                    break
                except Exception as e:
                    last_exc = e
                    continue

        if result is None:
            raise Exception(
                "Failed to fetch SMP data from NOGA SMP endpoints. "
                "Ensure the subscription key has access to TRADING/SMP or SMP/SMPAPI."
            ) from last_exc

        data = result.get("energy", result.get("data", []))
        _CACHE[cache_key] = {"data": data, "expires_at": now + _CACHE_TTL_SECONDS}
        return data
