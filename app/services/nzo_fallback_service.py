# app/services/nzo_fallback_service.py
"""
NZO Fallback Service — Alternative data source when NOGA API is down.

Uses the NZO mirror at https://data.nzo.org.il:8080/get
Documentation from client:
  - source is always noga2
  - type can be energy or co2emission
  - dates are DD-MM-YYYY
  - tag depends on type (Pv, Coal, Gas etc.)
  - time is all|hour|day|month (default: hour)
  - format can be csv|tsv|html|json|bin (default: json)
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

NZO_BASE_URL = "https://data.nzo.org.il:8080/get"
NZO_TIME_RESOLUTION_FIELD = "_nzo_time_resolution"

# Successful NZO responses are cached for this long. Same params -> same payload,
# so the FE can fire several charts at once without each one re-hitting NZO.
_CACHE_TTL_SECONDS = 300

# (expires_at, payload) keyed by canonical param string.
_RESPONSE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# In-flight requests keyed by canonical param string. When the FE fires the
# same query in parallel from multiple charts, only the first call actually
# hits NZO; the rest await the same future. This prevents the upstream from
# being hammered with duplicate concurrent requests.
_INFLIGHT: Dict[str, asyncio.Future] = {}


def _cache_key(params: Dict[str, str]) -> str:
    """Deterministic key from query params."""
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()))

# Map NZO energy key names → NOGA original key names
# NZO uses PascalCase; NOGA uses camelCase / mixed.
_NZO_ENERGY_KEY_MAP = {
    "ActualDemand": "actualDemand",
    "BatteriesNet": "batteries",
    "BioGas": "bio_Gas",
    "Coal": "coal",
    "Gas": "natural_Gas",
    "Mazut": "mazut",
    "Other": "other",
    "Psp": "pumpedStorage",
    "PspNet": "pumpedStorageBattery",
    "Pv": "photoVoltaic",
    "PvWithStorage": "photovoltaicIntegrated",
    "RenewableSum": "renewableSum",
    "Solar": "termo_Soler",
    "Storage": "storage",
    "Thermo": "thermo",
    "Wind": "wind",
}

# Map NZO CO2 key names → existing CO2 field names used in our codebase
_NZO_CO2_KEY_MAP = {
    "Co2CurrentDemand": "co2_current_demand",
    "Co2FromAllSitesWithoutRenewables": "co2_from_all_sites_without_renewables",
    "Co2Ratio": "co2_ratio",
    "Coal": "co2_coal",
    "Fueloil": "co2_fuel_oil",
    "Gas": "co2_gas",
    "Gasoil": "co2_diesel",
    "Methanol": "co2_methanol",
    "Renewables": "co2_renewables",
}

_NZO_SMP_KEY_MAP = {
    "PreBookingPriceConstrainedSmp": "day_Ahead_Constrained_Smp",
    "PreBookingPriceUnconstrainedSmp": "day_Ahead_Unconstrained_Smp",
    "RealTimePricingConstrainedSmp": "real_Time_Constrained_Smp",
    "RealTimePricingUnconstrainedSmp": "real_Time_Unconstrained_Smp",
}


class NZOFallbackService:
    """Fetches data from the NZO mirror of the NOGA API."""

    @staticmethod
    async def fetch_energy_data(
        start_date: str,
        end_date: str,
        time_resolution: str = "all",
        tag: Optional[str] = None,
    ) -> List[Dict]:
        """
        Fetch energy production data from NZO.

        Args:
            start_date: DD-MM-YYYY format
            end_date: DD-MM-YYYY format
            time_resolution: 'all' for 5-min samples, 'hour', 'day', or 'month'
            tag: Optional energy type filter (Pv, Coal, Gas, etc.)

        Returns:
            List of dicts matching the format expected by NogaService consumers,
            i.e. each dict has 'date', 'time', and energy field keys.
        """
        params: Dict[str, str] = {
            "source": "noga2",
            "type": "energy",
            "start_date": start_date,
            "end_date": end_date,
            "time": time_resolution,
            "format": "json",
        }
        if tag:
            params["tag"] = tag

        raw_json = await NZOFallbackService._do_request(params)

        # Parse the NZO response structure:
        # { "noga2.energy": { "DD-MM-YYYY": { "HH:MM": { ...fields... }, ... }, ... } }
        energy_data = raw_json.get("noga2.energy", {})
        return NZOFallbackService._flatten_nzo_energy(energy_data, time_resolution)

    @staticmethod
    async def fetch_co2_data(
        start_date: str,
        end_date: str,
        time_resolution: str = "hour",
    ) -> List[Dict]:
        """
        Fetch CO2 emission data from NZO.

        Returns:
            List of dicts with 'date', 'time', and CO2 field keys.
        """
        params: Dict[str, str] = {
            "source": "noga2",
            "type": "co2emission",
            "start_date": start_date,
            "end_date": end_date,
            "time": time_resolution,
            "format": "json",
        }

        raw_json = await NZOFallbackService._do_request(params)
        co2_data = raw_json.get("noga2.co2emission", {})
        return NZOFallbackService._flatten_nzo_co2(co2_data, time_resolution)

    @staticmethod
    async def fetch_smp_data(
        start_date: str,
        end_date: str,
        time_resolution: str = "all",
    ) -> List[Dict]:
        """
        Fetch SMP data from NZO and shape it like the NOGA SMP day payload.
        """
        params: Dict[str, str] = {
            "source": "noga2",
            "type": "smp",
            "start_date": start_date,
            "end_date": end_date,
            "time": time_resolution,
            "format": "json",
        }

        raw_json = await NZOFallbackService._do_request(params)
        smp_data = raw_json.get("noga2.smp", {})
        return NZOFallbackService._to_noga_smp_days(smp_data)

    @staticmethod
    async def fetch_demand_data(
        start_date: str,
        end_date: str,
        time_resolution: str = "all",
    ) -> List[Dict]:
        """
        Fetch demand from NZO energy ActualDemand and shape it like NOGA demand data.
        """
        energy_rows = await NZOFallbackService.fetch_energy_data(
            start_date=start_date,
            end_date=end_date,
            time_resolution=time_resolution,
        )
        return NZOFallbackService._to_noga_demand_days(energy_rows)

    @staticmethod
    async def _do_request(params: Dict[str, str]) -> Dict[str, Any]:
        """GET against NZO with response cache + request coalescing + retries.

        - Cache hit on identical params returns the cached payload (5-min TTL).
        - If another coroutine is already fetching the same params, we await
          its result instead of duplicating the call. This is the key fix for
          the page-load storm where 4+ charts request the same data in parallel.
        - The upstream call itself retries 4× with exponential backoff to ride
          out NZO's intermittent 5xx / connection resets.
        """
        key = _cache_key(params)
        now = time.time()

        cached = _RESPONSE_CACHE.get(key)
        if cached and cached[0] > now:
            return cached[1]

        # NB: the .get + assignment below run without an await in between, so
        # in asyncio's single-threaded model this is atomic.
        existing = _INFLIGHT.get(key)
        if existing is not None and not existing.done():
            return await existing

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        _INFLIGHT[key] = future

        try:
            payload = await NZOFallbackService._do_request_uncached(params)
            _RESPONSE_CACHE[key] = (time.time() + _CACHE_TTL_SECONDS, payload)
            future.set_result(payload)
            return payload
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            if _INFLIGHT.get(key) is future:
                _INFLIGHT.pop(key, None)

    @staticmethod
    async def _do_request_uncached(params: Dict[str, str]) -> Dict[str, Any]:
        """Raw HTTP call with exponential-backoff retries. Used by _do_request."""
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=15.0, pool=10.0)
        backoffs = (0.5, 1.0, 2.0)  # 4 total attempts
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(4):
                try:
                    response = await client.get(NZO_BASE_URL, params=params)
                    response.raise_for_status()
                    return response.json()
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "NZO attempt %d/4 failed (%s %s..%s): %s",
                        attempt + 1,
                        params.get("type", "?"),
                        params.get("start_date", "?"),
                        params.get("end_date", "?"),
                        exc,
                    )
                    if attempt < 3:
                        await asyncio.sleep(backoffs[attempt])

        raise Exception(
            f"NZO fallback failed after 4 attempts: {last_exc}"
        ) from last_exc

    @staticmethod
    def _flatten_nzo_energy(data: Dict[str, Dict], time_resolution: str) -> List[Dict]:
        """
        Convert NZO energy response to flat list matching NOGA format.

        NZO format: { "DD-MM-YYYY": { "HH:MM": { fields }, ... }, ... }
        Output:     [ { "date": "DD-MM-YYYY", "time": "HH:MM:SS", ...fields... }, ... ]
        """
        flattened: List[Dict] = []
        for date_str, time_entries in data.items():
            if not isinstance(time_entries, dict):
                continue
            for time_str, fields in time_entries.items():
                if not isinstance(fields, dict):
                    continue
                record: Dict[str, Any] = {
                    "date": date_str,
                    "time": f"{time_str}:00" if len(time_str) <= 5 else time_str,
                    NZO_TIME_RESOLUTION_FIELD: time_resolution,
                }
                # Map NZO keys to NOGA keys
                for nzo_key, noga_key in _NZO_ENERGY_KEY_MAP.items():
                    if nzo_key in fields:
                        record[noga_key] = fields[nzo_key]
                flattened.append(record)

        # Sort by date + time for consistent ordering
        flattened.sort(key=lambda r: (r.get("date", ""), r.get("time", "")))
        return flattened

    @staticmethod
    def _to_noga_smp_days(data: Dict[str, Dict]) -> List[Dict]:
        """
        Convert NZO SMP response to the day/list structure used by SMP processors.
        """
        days: List[Dict] = []
        for date_str, time_entries in sorted(data.items()):
            if not isinstance(time_entries, dict):
                continue
            samples: List[Dict] = []
            for time_str, fields in sorted(time_entries.items()):
                if not isinstance(fields, dict):
                    continue
                sample: Dict[str, Any] = {
                    "time": f"{time_str}:00" if len(time_str) <= 5 else time_str,
                }
                for nzo_key, noga_key in _NZO_SMP_KEY_MAP.items():
                    if nzo_key in fields:
                        sample[noga_key] = fields[nzo_key]
                samples.append(sample)
            if samples:
                days.append({"date": date_str, "smpData": samples})
        return days

    @staticmethod
    def _to_noga_demand_days(rows: List[Dict]) -> List[Dict]:
        """
        Convert flattened NZO energy rows to the day/list structure used by DemandService.
        """
        by_date: Dict[str, List[Dict]] = {}
        for row in rows:
            date_str = row.get("date")
            time_str = row.get("time")
            if not date_str or not time_str:
                continue
            actual_demand = row.get("actualDemand")
            if actual_demand is None:
                continue
            by_date.setdefault(date_str, []).append(
                {
                    "time": time_str,
                    "demandCurrent": actual_demand,
                }
            )

        return [
            {"date": date_str, "demandData": sorted(samples, key=lambda s: s.get("time", ""))}
            for date_str, samples in sorted(by_date.items())
        ]

    @staticmethod
    def _flatten_nzo_co2(data: Dict[str, Dict], time_resolution: str) -> List[Dict]:
        """
        Convert NZO CO2 response to flat list.

        NZO format: { "DD-MM-YYYY": { "HH:MM": { fields }, ... }, ... }
        Output:     [ { "date": "DD-MM-YYYY", "time": "HH:MM:SS", ...fields... }, ... ]
        """
        flattened: List[Dict] = []
        for date_str, time_entries in data.items():
            if not isinstance(time_entries, dict):
                continue
            for time_str, fields in time_entries.items():
                if not isinstance(fields, dict):
                    continue
                record: Dict[str, Any] = {
                    "date": date_str,
                    "time": f"{time_str}:00" if len(time_str) <= 5 else time_str,
                    NZO_TIME_RESOLUTION_FIELD: time_resolution,
                }
                for nzo_key, mapped_key in _NZO_CO2_KEY_MAP.items():
                    if nzo_key in fields:
                        record[mapped_key] = fields[nzo_key]
                flattened.append(record)

        flattened.sort(key=lambda r: (r.get("date", ""), r.get("time", "")))
        return flattened
