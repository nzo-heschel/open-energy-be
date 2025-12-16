import json
from datetime import datetime, timedelta
import re
from typing import Dict, List

from http.client import IncompleteRead

import anyio
import requests
from fastapi import HTTPException
from requests.exceptions import ChunkedEncodingError
from urllib3.exceptions import ProtocolError

from app.config import get_proxies
BASE_URL = "https://apim-api.noga-iso.co.il/"


def to_snake_case(s: str) -> str:
    s = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", s)
    s = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


class NogaService:
    @staticmethod
    async def fetch_production_mix(start: str, end: str, token: str) -> List[Dict]:
        """
        Fetch production mix from NOGA API.
        start, end: 'dd-mm-yyyy'
        token: NOGA API token
        """
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

        proxies = get_proxies()

        def _flatten_energy(result: Dict) -> List[Dict]:
            energy = result.get("energy", [])
            values: List[Dict] = []
            for day_item in energy:
                date = day_item.get("date")
                time_items = day_item[list(day_item.keys())[1]]  # second key has time data
                for time_item in (time_items or []):
                    value = {"date": date}
                    value.update(time_item)
                    values.append(value)
            return values

        def _do_request(range_start: str, range_end: str, stream: bool = True) -> Dict:
            payload = {"fromDate": range_start, "toDate": range_end}
            last_exc = None
            for attempt in range(3):
                try:
                    resp = requests.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=(10, 90),  # connect, read
                        proxies=proxies,
                        stream=stream,  # avoid early full download
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
        Aggregate energy values into Non-renewables, Renewables, Other for chart display
        """
        agg = {
            "Non-renewables": 0,
            "Renewables": 0,
            "Other": 0
        }

        for v in values:
            agg["Non-renewables"] += sum([
                v.get("coal", 0),
                v.get("natural_gas", 0),
                v.get("mazut", 0)  # diesel
            ])
            agg["Renewables"] += sum([
                v.get("photovoltaic", 0),
                v.get("biogas", 0),
                v.get("wind", 0),
                v.get("termo_soler", 0),
                v.get("photovoltaic_integrated", 0)
            ])
            agg["Other"] += sum([
                v.get("other", 0),
                v.get("pumped_storage", 0)
            ])

        return agg
