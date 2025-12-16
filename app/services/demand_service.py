import os
import time
from datetime import datetime
from typing import Dict, List

import httpx

BASE_URL = "https://apim-api.noga-iso.co.il/"
DEMAND_PATHS = [
    "DEMAND/DEMANDAPI/v1",
    "demand/demandapi/v1",
]
_CACHE: Dict[tuple[str, str, str], Dict] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _iso_timestamp(date_str: str, time_str: str | None) -> str:
    """
    Convert date + time strings from NOGA into ISO 8601 timestamp strings.
    """
    time_str = time_str or "00:00"
    candidates = [
        ("%d-%m-%Y %H:%M:%S", f"{date_str} {time_str}"),
        ("%d-%m-%Y %H:%M", f"{date_str} {time_str}"),
        ("%Y-%m-%d %H:%M:%S", f"{date_str} {time_str}"),
        ("%Y-%m-%d %H:%M", f"{date_str} {time_str}"),
    ]
    for fmt, value in candidates:
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            continue
    return f"{date_str}T{time_str}"


class DemandService:
    @staticmethod
    async def fetch_demand_data(start: str, end: str, token: str | None = None) -> List[Dict]:
        """
        Fetch demand data from the NOGA demand endpoint with short-term caching.
        """
        tokens_to_try: list[str] = []
        if token:
            tokens_to_try.append(token)
        env_demand = os.getenv("DEMAND_TOKEN")
        env_noga = os.getenv("NOGA_API_TOKEN")
        for t in (env_demand, env_noga):
            if t and t not in tokens_to_try:
                tokens_to_try.append(t)

        if not tokens_to_try:
            raise Exception("No demand token configured. Set DEMAND_TOKEN or NOGA_API_TOKEN.")

        now = time.time()
        for t in tokens_to_try:
            cache_key = (start, end, t)
            cached = _CACHE.get(cache_key)
            if cached and cached["expires_at"] > now:
                return cached["data"]

        headers_base = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

        last_exc: Exception | None = None
        last_status: int | None = None
        last_body: str | None = None
        last_path: str | None = None
        result = None
        used_token: str | None = None

        timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            for candidate_token in tokens_to_try:
                headers = {**headers_base, "Ocp-Apim-Subscription-Key": candidate_token}
                for path in DEMAND_PATHS:
                    try:
                        response = await client.post(path, headers=headers, json={"fromDate": start, "toDate": end})
                        response.raise_for_status()
                        result = response.json()
                        used_token = candidate_token
                        break
                    except Exception as exc:
                        last_exc = exc
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
            detail = "Failed to fetch demand data from NOGA DEMAND endpoints."
            if last_status:
                detail += f" Last response ({last_path}): {last_status} {last_body or ''}".strip()
            raise Exception(detail) from last_exc

        data = result if isinstance(result, list) else result.get("data", [])
        if used_token:
            _CACHE[(start, end, used_token)] = {"data": data, "expires_at": time.time() + _CACHE_TTL_SECONDS}
        return data

    @staticmethod
    def to_demand_lookup(demand_data: List[Dict]) -> Dict[str, float]:
        """
        Flatten demand payload into a timestamp->demandCurrent mapping.
        """
        lookup: Dict[str, float] = {}
        days = demand_data if isinstance(demand_data, list) else demand_data.get("data", [])
        for day in days:
            date_str = day.get("date") or day.get("day") or ""
            samples = day.get("demandData") or day.get("data") or []
            for sample in samples:
                ts = _iso_timestamp(date_str, sample.get("time"))
                demand_val = sample.get("demandCurrent") or sample.get("demandUpdated") or sample.get("demandHead")
                try:
                    demand_val = float(demand_val)
                except (TypeError, ValueError):
                    continue
                lookup[ts] = demand_val
        return lookup
