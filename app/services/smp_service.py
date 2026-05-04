import json
import os
import time
from typing import Dict, List
import httpx

# from app.config import PROXY_VERIFY_SSL, configure_global_proxy, get_proxies

BASE_URL = "https://apim-api.noga-iso.co.il/"
_CACHE: Dict[tuple[str, str, str | None], Dict] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes to avoid hammering the external API
SMP_PATHS = [
    "SMP/SMPAPI/v1",            # primary SMP endpoint (confirmed)
    "TRADING/SMP/v1",           # legacy path
    "trade/smp/v1",             # lowercase path variants
    "trading/smp/v1",
]


class SMPService:
    @staticmethod
    async def fetch_smp_data(start: str, end: str, token: str | None) -> List[Dict]:
        # Ensure proxies are applied when the module is used directly.
        # configure_global_proxy()

        # Build a list of tokens to try (explicit token, then env fallbacks).
        tokens_to_try: list[str] = []
        if token:
            tokens_to_try.append(token)
        env_smp = os.getenv("SMP_TOKEN")
        env_noga = os.getenv("NOGA_API_TOKEN")
        for t in (env_smp, env_noga):
            if t and t not in tokens_to_try:
                tokens_to_try.append(t)

        now = time.time()
        for t in tokens_to_try:
            cache_key = (start, end, t)
            cached = _CACHE.get(cache_key)
            if cached and cached["expires_at"] > now:
                return cached["data"]
        cached_fallback = _CACHE.get((start, end, "__nzo_fallback__"))
        if not tokens_to_try and cached_fallback and cached_fallback["expires_at"] > now:
            return cached_fallback["data"]

        if not tokens_to_try:
            return await SMPService._fetch_from_nzo(start, end)

        headers_base = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }
        # proxies = get_proxies()
        # trust_env = proxies is None

        last_exc: Exception | None = None
        last_status: int | None = None
        last_body: str | None = None
        last_path: str | None = None
        result = None
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
        used_token: str | None = None

        async with httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            # trust_env=trust_env,  # honor HTTP(S)_PROXY when set via env
            # proxies=proxies,
            # verify=PROXY_VERIFY_SSL,
        ) as client:
            for candidate_token in tokens_to_try:
                headers = {**headers_base, "Ocp-Apim-Subscription-Key": candidate_token}
                for path in SMP_PATHS:
                    try:
                        response = await client.post(path, headers=headers, json={"fromDate": start, "toDate": end})
                        response.raise_for_status()
                        result = response.json()
                        used_token = candidate_token
                        break
                    except Exception as e:
                        last_exc = e
                        last_path = path
                        if "response" in locals():
                            last_status = response.status_code
                            try:
                                last_body = response.text
                            except Exception:
                                last_body = None
                        continue
                if result is not None:
                    break

        if result is None:
            detail = (
                "Failed to fetch SMP data from NOGA SMP endpoints. "
                "Ensure the subscription key has access to TRADING/SMP or SMP/SMPAPI."
            )
            if last_status:
                detail += f" Last response ({last_path}): {last_status} {last_body or ''}".strip()
            try:
                return await SMPService._fetch_from_nzo(start, end)
            except Exception as nzo_exc:
                raise Exception(
                    f"Both NOGA SMP API and NZO fallback failed. NOGA: {detail}. NZO: {nzo_exc}"
                ) from nzo_exc

        # Normalize payloads from different NOGA SMP responses.
        if isinstance(result, list):
            data = result
        else:
            data = (
                result.get("energy")
                or result.get("data")
                or result.get("smpData")
                or []
            )
            if isinstance(data, dict):
                data = (
                    data.get("energy")
                    or data.get("data")
                    or data.get("smpData")
                    or []
                )

        if used_token:
            _CACHE[(start, end, used_token)] = {"data": data, "expires_at": time.time() + _CACHE_TTL_SECONDS}
        if not data:
            return await SMPService._fetch_from_nzo(start, end)
        return data

    @staticmethod
    async def _fetch_from_nzo(start: str, end: str) -> List[Dict]:
        from app.services.nzo_fallback_service import NZOFallbackService

        cache_key = (start, end, "__nzo_fallback__")
        cached = _CACHE.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]

        data = await NZOFallbackService.fetch_smp_data(
            start_date=start,
            end_date=end,
            time_resolution="all",
        )
        _CACHE[cache_key] = {"data": data, "expires_at": time.time() + _CACHE_TTL_SECONDS}
        return data
