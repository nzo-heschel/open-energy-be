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

logger = logging.getLogger(__name__)

# Proxy helpers disabled while running without a proxy/VPN.
# from app.config import (
#     PROXY_VERIFY_SSL,
#     configure_global_proxy,
#     get_proxy_auth,
#     get_proxies,
# )
BASE_URL = "https://apim-api.noga-iso.co.il/"


class NogaService:
    @staticmethod
    async def fetch_production_mix(start: str, end: str, token: str) -> List[Dict]:
        """
        Fetch production mix from NOGA API with NZO fallback.
        start, end: 'dd-mm-yyyy'
        token: NOGA API token
        """
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
        return await NZOFallbackService.fetch_energy_data(
            start_date=start,
            end_date=end,
            time_resolution="hour",
        )

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
            ])
            agg["Renewables"] += sum([
                v.get("photoVoltaic", 0),
                v.get("bio_Gas", 0),
                v.get("wind", 0),
                v.get("termo_Soler", 0),
                v.get("photovoltaicIntegrated", 0),
                v.get("pv_storage", 0),
                v.get("photovoltaic_storage", 0),
                # "storage" field dropped per client request
                # "batteries" moved to Other
            ])
            agg["Other"] += sum([
                v.get("other", 0),
                v.get("batteries", 0),
                v.get("pumpedStorage", 0),
                v.get("pumpedStorageBattery", 0),
            ])

        return agg
