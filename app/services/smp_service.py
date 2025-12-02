import json
import time
from typing import Dict, List
import httpx

BASE_URL = "https://apim-api.noga-iso.co.il/"
_CACHE: Dict[tuple[str, str], Dict] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes to avoid hammering the external API


class SMPService:
    @staticmethod
    async def fetch_smp_data(start: str, end: str, token: str) -> List[Dict]:
        """
        Fetch SMP data from the NOGA API using an async client and short-term caching.
        """
        cache_key = (start, end)
        now = time.time()
        cached = _CACHE.get(cache_key)
        if cached and cached["expires_at"] > now:
            return cached["data"]

        path = "PRODUCTIONMIX/PRODMIXAPI/v1"  # Adjust if SMP path differs
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Ocp-Apim-Subscription-Key": token,
        }

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
            try:
                response = await client.post(path, headers=headers, json={"fromDate": start, "toDate": end})
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                raise Exception(f"Error fetching SMP data: {e}") from e

        data = result.get("energy", result.get("data", []))
        _CACHE[cache_key] = {"data": data, "expires_at": now + _CACHE_TTL_SECONDS}
        return data
