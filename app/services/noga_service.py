import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from http.client import IncompleteRead

import anyio
import requests
from fastapi import HTTPException
from requests.exceptions import ChunkedEncodingError
from urllib3.exceptions import ProtocolError

from app.services.noga_source_mode import use_nzo_fallback_only

logger = logging.getLogger(__name__)

# Proxy helpers disabled while running without a proxy/VPN.
# from app.config import (
#     PROXY_VERIFY_SSL,
#     configure_global_proxy,
#     get_proxy_auth,
#     get_proxies,
# )
BASE_URL = "https://apim-api.noga-iso.co.il/"


# NOGA renamed many production-mix fields in June 2026. To keep every
# downstream consumer (energy_overview, renewable_mix, renewable_transition,
# renewable_potential, heat_load_vs_generation, smp_production, the CO2
# services, and the /production-mix endpoint) working without touching each
# one, we mirror every renamed field back to its historical name in the
# flattened sample. Old code that does ``sample.get("photoVoltaic", 0)``
# continues to work unchanged.
#
# Mapping is intentionally conservative — only fields with a clear semantic
# equivalent are mirrored. Net fields that the client previously asked us to
# EXCLUDE stay unmapped so they don't accidentally re-enter the totals:
#   - pump_Gen_PumpedStorage  (net PSP — client wants gross only)
#   - discharge_Charge_BESS   (net BESS — excluded per client)
#   - discharge_PumpedStorage_and_BESS  (bundled storage discharge)
#   - demand_Management       (no equivalent in old schema)
#
# NOGA's own ``total_Renewables`` includes ``thermo_Solar``, so we mirror
# it onto the existing ``thermo`` key (a renewable in our schema) — matching
# NOGA's classification and the gov dashboard's totals.
_NOGA_NEW_TO_OLD_KEYS = {
    "pv": "photoVoltaic",
    "discharge_PV_BESS": "photovoltaicIntegrated",
    "thermo_Solar": "thermo",
    "gas_Oil": "diesel",
    "oil": "mazut",
    "total_Renewables": "renewableSum",
    "demand": "actualDemand",
}


def _normalize_noga_sample(sample: Dict) -> Dict:
    """Mirror NOGA's new field names onto the historical names.

    Mutates and returns ``sample``. Does NOT overwrite an existing
    historical key, so samples that already carry both names (e.g. from a
    transitional NOGA response) keep their original value.
    """
    for new_key, old_key in _NOGA_NEW_TO_OLD_KEYS.items():
        if new_key in sample and old_key not in sample:
            sample[old_key] = sample[new_key]
    return sample


class NogaService:
    @staticmethod
    async def fetch_production_mix(start: str, end: str, token: str | None) -> List[Dict]:
        """
        Fetch production mix from NOGA API with NZO fallback.
        start, end: 'dd-mm-yyyy'
        token: NOGA API token
        """
        if use_nzo_fallback_only():
            return await NogaService._fetch_from_nzo(start, end)

        # Try NOGA first, fall back to NZO if NOGA fails
        try:
            return await NogaService._fetch_from_noga(start, end, token)
        except Exception as noga_exc:
            logger.warning("NOGA API failed, trying NZO fallback: %s", noga_exc)
            try:
                return await NogaService._fetch_from_nzo(start, end)
            except Exception as nzo_exc:
                logger.error("NZO fallback also failed: %s", nzo_exc)
                # Re-raise the original NOGA error with note about NZO
                raise HTTPException(
                    status_code=424,
                    detail=(
                        f"Both NOGA API and NZO fallback failed. "
                        f"NOGA: {noga_exc}. NZO: {nzo_exc}"
                    ),
                ) from nzo_exc

    @staticmethod
    async def _fetch_from_nzo(start: str, end: str) -> List[Dict]:
        """Fetch from NZO fallback service using hourly resolution for speed.

        Using time=hour returns 24 records/day instead of 288 (time=all).
        The values are the sum of 12 five-minute MW readings per hour.
        Dividing by 12 still gives correct MWh per hour.
        """
        from app.services.nzo_fallback_service import NZOFallbackService

        start_dt = datetime.strptime(start, "%d-%m-%Y").date()
        end_dt = datetime.strptime(end, "%d-%m-%Y").date()
        if (end_dt - start_dt).days <= 31:
            return await NZOFallbackService.fetch_energy_data(
                start_date=start,
                end_date=end,
                time_resolution="hour",
            )

        dedup: dict[tuple[str, str], Dict] = {}
        cur = start_dt
        while cur <= end_dt:
            chunk_end = min(cur + timedelta(days=30), end_dt)
            chunk_rows = await NZOFallbackService.fetch_energy_data(
                start_date=cur.strftime("%d-%m-%Y"),
                end_date=chunk_end.strftime("%d-%m-%Y"),
                time_resolution="hour",
            )
            for row in chunk_rows:
                date = row.get("date")
                time = row.get("time")
                if date and time:
                    dedup[(date, time)] = row
            cur = chunk_end + timedelta(days=1)

        return list(dedup.values())

    @staticmethod
    async def _fetch_from_noga(start: str, end: str, token: str) -> List[Dict]:
        """Original NOGA API fetch logic."""
        # configure_global_proxy()
        path = "PRODUCTIONMIX/PRODMIXAPI/v1"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Accept": "application/json",
            # Avoid compressed chunked transfer that occasionally breaks via proxy.
            "Accept-Encoding": "identity",
            "Ocp-Apim-Subscription-Key": token,
        }
        url = BASE_URL + path

        # proxies = get_proxies()
        # proxy_auth = get_proxy_auth()

        def _flatten_energy(result: Dict) -> List[Dict]:
            energy = result.get("energy", [])
            values: List[Dict] = []
            for day_item in energy:
                date = day_item.get("date")
                time_items = day_item[list(day_item.keys())[1]]  # second key has time data
                for time_item in time_items:
                    value = {"date": date}
                    value.update(time_item)
                    _normalize_noga_sample(value)
                    values.append(value)
            return values

        def _do_request(range_start: str, range_end: str, stream: bool = True) -> Dict:
            payload = {"fromDate": range_start, "toDate": range_end}
            last_exc = None
            for attempt in range(1):  # single attempt — fail fast to NZO fallback
                try:
                    resp = requests.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=(5, 15),  # connect 5s, read 15s — fast fail
                        # proxies=proxies,
                        # auth=proxy_auth,
                        stream=stream,  # avoid early full download
                        # verify=PROXY_VERIFY_SSL,
                    )
                    # If proxy/NOGA rejects, surface a clean HTTPException.
                    try:
                        resp.raise_for_status()
                    except requests.HTTPError as exc:
                        raise HTTPException(
                            status_code=resp.status_code,
                            detail=f"NOGA API error ({resp.status_code}): {resp.text[:200]}",
                        ) from exc

                    # Read fully to catch chunked errors early.
                    content = resp.content  # noqa: B113
                    return resp.json()
                except (ChunkedEncodingError, IncompleteRead, ProtocolError) as exc:
                    last_exc = exc
                    if attempt < 2:
                        continue
                    raise HTTPException(
                        status_code=424,
                        detail="Upstream NOGA response was truncated; please retry.",
                    ) from exc
                except HTTPException:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt < 2:
                        continue
                    raise HTTPException(
                        status_code=424,
                        detail=f"Error fetching NOGA data: {exc}",
                    ) from exc
            raise HTTPException(
                status_code=424,
                detail=f"Error fetching NOGA data: {last_exc}",
            ) from last_exc

        def _fetch_in_slices() -> List[Dict]:
            start_dt = datetime.strptime(start, "%d-%m-%Y").date()
            end_dt = datetime.strptime(end, "%d-%m-%Y").date()
            dedup: dict[tuple[str, str], Dict] = {}

            cur = start_dt
            while cur <= end_dt:
                slice_end_dt = min(cur + timedelta(days=29), end_dt)
                slice_start_str = cur.strftime("%d-%m-%Y")
                slice_end_str = slice_end_dt.strftime("%d-%m-%Y")
                slice_result = _do_request(slice_start_str, slice_end_str, stream=False)
                for val in _flatten_energy(slice_result):
                    key = (val.get("date"), val.get("time"))
                    if key[0] and key[1]:
                        dedup[key] = val
                cur = slice_end_dt + timedelta(days=1)
            return list(dedup.values())

        try:
            result = await anyio.to_thread.run_sync(lambda: _do_request(start, end, True))
            return _flatten_energy(result)
        except HTTPException as exc:
            # On truncated/stream errors, fall back to smaller window slices.
            if exc.status_code == 424:
                return await anyio.to_thread.run_sync(_fetch_in_slices)
            raise
        except Exception as exc:  # noqa: BLE001
            raise Exception(f"Error fetching NOGA data: {exc}") from exc

    @staticmethod
    def aggregate_energy(values: List[Dict]) -> Dict:
        """
        Aggregate energy values into Non-renewables, Renewables, Other for chart display.
        diesel (Soler) and fuel_oil (Mazout) are tracked separately.
        batteries and pumped_storage are distinct standalone fields under Other.
        """
        agg = {
            "Non-renewables": 0,
            "Renewables": 0,
            "Other": 0
        }

        for v in values:
            agg["Non-renewables"] += sum([
                v.get("coal", 0),
                v.get("natural_Gas", 0),
                v.get("mazut", 0),       # fuel_oil
                v.get("diesel", 0),      # diesel
                v.get("Diesel", 0),
                v.get("termo_Soler", 0), # thermal solar — classified as non-renewable per client
            ])
            agg["Renewables"] += sum([
                v.get("photoVoltaic", 0),
                v.get("bio_Gas", 0),
                v.get("wind", 0),
                v.get("photovoltaicIntegrated", 0),
                v.get("pv_storage", 0),
                v.get("photovoltaic_storage", 0),
                v.get("thermo", 0),       # NZO Thermo — renewable per client
                v.get("Thermo", 0),
                # "storage" field dropped per client request
                # "termo_Soler" (NZO Solar) classified as non-renewable per client
            ])
            agg["Other"] += sum([
                v.get("other", 0),
                v.get("pumpedStorage", 0),
                # "batteries"/BatteriesNet and pumpedStorageBattery (PspNet) excluded per client
            ])

        return agg
