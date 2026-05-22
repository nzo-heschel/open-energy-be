import os
import time
from datetime import datetime
from typing import Dict, List

import httpx

from app.services.noga_source_mode import use_nzo_fallback_only

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
        if use_nzo_fallback_only():
            return await DemandService._fetch_from_nzo(start, end)

        tokens_to_try: list[str] = []
        if token:
            tokens_to_try.append(token)
        env_demand = os.getenv("DEMAND_TOKEN")
        env_noga = os.getenv("NOGA_API_TOKEN")
        for t in (env_demand, env_noga):
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
            return await DemandService._fetch_from_nzo(start, end)

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
            try:
                return await DemandService._fetch_from_nzo(start, end)
            except Exception as nzo_exc:
                raise Exception(
                    f"Both NOGA demand API and NZO fallback failed. NOGA: {detail}. NZO: {nzo_exc}"
                ) from nzo_exc

        data = result if isinstance(result, list) else result.get("data", [])
        if used_token:
            _CACHE[(start, end, used_token)] = {"data": data, "expires_at": time.time() + _CACHE_TTL_SECONDS}
        if not data:
            return await DemandService._fetch_from_nzo(start, end)
        return data

    @staticmethod
    async def _fetch_from_nzo(start: str, end: str) -> List[Dict]:
        from app.services.nzo_fallback_service import NZOFallbackService

        cache_key = (start, end, "__nzo_fallback__")
        cached = _CACHE.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]

        data = await NZOFallbackService.fetch_demand_data(
            start_date=start,
            end_date=end,
            time_resolution="all",
        )
        _CACHE[cache_key] = {"data": data, "expires_at": time.time() + _CACHE_TTL_SECONDS}
        return data

    @staticmethod
    def to_demand_lookup(
        demand_data: List[Dict],
        window_minutes: int | None = None,
    ) -> Dict[str, float]:
        """
        Flatten demand payload into a timestamp -> value lookup.

        ``window_minutes=None`` (default, backwards-compatible) keeps the lookup
        keyed by the exact sample timestamp — i.e. a 5-min snapshot. This is
        wrong for charts whose buckets are coarser than the demand resolution:
        e.g. SMP is half-hourly, so pairing each SMP bin with a single 5-min
        demand snapshot at the bin's *start* misrepresents the bin (00:00
        snapshot 8760 MW vs the true 00:00–00:30 average 8674 MW).

        Pass ``window_minutes=W`` to fix this: every demand sample is floored
        to the start of its W-minute window, and the returned lookup value at
        each *window anchor* is the **mean of all demand samples falling in
        [anchor, anchor + W)**. SMP services should pass ``window_minutes=30``
        because each SMP price represents the half-hour beginning at its
        timestamp, so the demand paired with it must also span that half-hour.
        """
        if window_minutes is None:
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

        if window_minutes <= 0:
            raise ValueError("window_minutes must be a positive integer")

        from collections import defaultdict
        from datetime import datetime as _dt

        buckets: Dict[str, list[float]] = defaultdict(list)
        days = demand_data if isinstance(demand_data, list) else demand_data.get("data", [])
        for day in days:
            date_str = day.get("date") or day.get("day") or ""
            samples = day.get("demandData") or day.get("data") or []
            for sample in samples:
                ts = _iso_timestamp(date_str, sample.get("time"))
                try:
                    dt = _dt.fromisoformat(ts)
                except ValueError:
                    continue
                demand_val = sample.get("demandCurrent") or sample.get("demandUpdated") or sample.get("demandHead")
                try:
                    demand_val = float(demand_val)
                except (TypeError, ValueError):
                    continue
                # Floor to window boundary; e.g. for 30-min windows the bin
                # is [00:00, 00:30) — a sample at 00:30 floors to its own
                # 00:30 anchor (right-exclusive), matching SMP convention.
                mins = dt.hour * 60 + dt.minute
                anchor_min = (mins // window_minutes) * window_minutes
                anchor = dt.replace(
                    hour=anchor_min // 60,
                    minute=anchor_min % 60,
                    second=0,
                    microsecond=0,
                )
                buckets[anchor.isoformat()].append(demand_val)
        return {anchor: sum(vs) / len(vs) for anchor, vs in buckets.items() if vs}
