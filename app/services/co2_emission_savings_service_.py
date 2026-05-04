# app/services/noga_co2_service.py
import logging
import os
import time
from typing import Any, Dict, List, Tuple, Optional
import httpx

from app.services.noga_source_mode import use_nzo_fallback_only

logger = logging.getLogger(__name__)

BASE_URL = "https://apim-api.noga-iso.co.il/"
CO2_PATH = "CO2/CO2aPI/v1"

_CACHE: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 300


class NogaCO2Service:
    @staticmethod
    def _build_tokens_to_try(explicit_token: Optional[str]) -> list[str]:
        tokens: list[str] = []
        if explicit_token:
            tokens.append(explicit_token)

        # ✅ Your actual env name
        env_co2 = os.getenv("CO2_TOKEN")
        if env_co2 and env_co2 not in tokens:
            tokens.append(env_co2)

        # optional fallbacks (safe to keep)
        for env_name in ("NOGA_SUBSCRIPTION_KEY", "NOGA_API_TOKEN"):
            v = os.getenv(env_name)
            if v and v not in tokens:
                tokens.append(v)

        return tokens

    @staticmethod
    def _flatten_co2_data(payload: Dict) -> List[Dict]:
        """
        Flatten the nested CO2 API response structure.
        The API returns: { "co2": [ { "date": "...", "<time_key>": [ {...time data...} ] }, ... ] }
        We flatten it to: [ { "date": "...", "time": "...", ...other fields... }, ... ]
        Similar to the production mix API's energy flattening.
        """
        co2_list = payload.get("co2", [])
        if not isinstance(co2_list, list):
            return []
        
        flattened: List[Dict] = []
        for day_item in co2_list:
            if not isinstance(day_item, dict):
                continue
            date = day_item.get("date")
            
            # Find the time data key (it's the second key after "date")
            for key, value in day_item.items():
                if key == "date":
                    continue
                if isinstance(value, list):
                    # This is the time data list
                    for time_item in value:
                        if isinstance(time_item, dict):
                            record = {"date": date}
                            record.update(time_item)
                            flattened.append(record)
                    break  # Only process the first list key
        
        return flattened

    @staticmethod
    async def fetch_co2_data(from_date: str, to_date: str, subscription_key: Optional[str] = None) -> List[Dict]:
        """Fetch CO2 data from NOGA API with NZO fallback."""
        if use_nzo_fallback_only():
            from app.services.nzo_fallback_service import NZOFallbackService
            return await NZOFallbackService.fetch_co2_data(
                start_date=from_date,
                end_date=to_date,
                time_resolution="hour",
            )

        try:
            return await NogaCO2Service._fetch_from_noga(from_date, to_date, subscription_key)
        except Exception as noga_exc:
            logger.warning("NOGA CO2 API failed, trying NZO fallback: %s", noga_exc)
            try:
                from app.services.nzo_fallback_service import NZOFallbackService
                return await NZOFallbackService.fetch_co2_data(
                    start_date=from_date,
                    end_date=to_date,
                    time_resolution="hour",
                )
            except Exception as nzo_exc:
                logger.error("NZO CO2 fallback also failed: %s", nzo_exc)
                raise Exception(
                    f"Both NOGA CO2 API and NZO fallback failed. "
                    f"NOGA: {noga_exc}. NZO: {nzo_exc}"
                ) from nzo_exc

    @staticmethod
    async def _fetch_from_noga(from_date: str, to_date: str, subscription_key: Optional[str] = None) -> List[Dict]:
        """Original NOGA CO2 fetch logic."""
        tokens_to_try = NogaCO2Service._build_tokens_to_try(subscription_key)
        if not tokens_to_try:
            raise Exception("No CO2 token configured. Set CO2_TOKEN in .env")

        now = time.time()
        for t in tokens_to_try:
            cache_key = (from_date, to_date, t)
            cached = _CACHE.get(cache_key)
            if cached and cached["expires_at"] > now:
                return cached["data"]

        headers_base = {"Content-Type": "application/json", "Cache-Control": "no-cache"}

        last_exc: Exception | None = None
        last_status: int | None = None
        last_body: str | None = None

        timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            for candidate_token in tokens_to_try:
                headers = {**headers_base, "Ocp-Apim-Subscription-Key": candidate_token}
                try:
                    resp = await client.post(CO2_PATH, headers=headers, json={"fromDate": from_date, "toDate": to_date})
                    resp.raise_for_status()
                    payload = resp.json()

                    # Handle different response structures
                    if isinstance(payload, list):
                        data = payload
                    elif isinstance(payload, dict):
                        # Check for "co2" key first (the actual NOGA CO2 API response structure)
                        if "co2" in payload:
                            data = NogaCO2Service._flatten_co2_data(payload)
                        else:
                            # Fallback to other common structures
                            data = payload.get("data") or payload.get("result") or []
                            if isinstance(data, dict):
                                data = data.get("data") or data.get("items") or data.get("rows") or []
                    else:
                        data = []

                    if not isinstance(data, list):
                        data = []

                    _CACHE[(from_date, to_date, candidate_token)] = {
                        "data": data,
                        "expires_at": time.time() + _CACHE_TTL_SECONDS,
                    }
                    return data
                except Exception as e:
                    last_exc = e
                    try:
                        last_status = resp.status_code
                        last_body = resp.text
                    except Exception:
                        pass
                    continue

        detail = "Failed to fetch CO2 data from NOGA CO2 endpoint."
        if last_status:
            detail += f" Last response: {last_status} {last_body or ''}".strip()
        raise Exception(detail) from last_exc
