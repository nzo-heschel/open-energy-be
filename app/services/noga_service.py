import json
import urllib.request
from datetime import datetime
from typing import List, Dict

BASE_URL = "https://apim-api.noga-iso.co.il/"

class NogaService:
    @staticmethod
    async def fetch_production_mix(start: str, end: str, token: str) -> List[Dict]:
        """
        Fetch production mix from NOGA API.
        start, end: 'dd-mm-yyyy'
        token: NOGA API token
        """
        path = "PRODUCTIONMIX/PRODMIXAPI/v1"
        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'Ocp-Apim-Subscription-Key': token
        }
        data = json.dumps({"fromDate": start, "toDate": end})
        req = urllib.request.Request(BASE_URL + path, headers=headers, data=bytes(data.encode("utf-8")))
        req.get_method = lambda: 'POST'

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            raise Exception(f"Error fetching NOGA data: {e}")

        # Flatten the nested structure
        energy = result.get("energy", [])
        values = []
        for day_item in energy:
            date = day_item.get("date")
            time_items = day_item[list(day_item.keys())[1]]  # second key has time data
            for time_item in time_items:
                value = {"date": date}
                value.update(time_item)
                values.append(value)

        return values

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
                v.get("natural_Gas", 0),
                v.get("mazut", 0)  # diesel
            ])
            agg["Renewables"] += sum([
                v.get("photoVoltaic", 0),
                v.get("bio_Gas", 0),
                v.get("wind", 0),
                v.get("termo_Soler", 0),
                v.get("photovoltaicIntegrated", 0)
            ])
            agg["Other"] += sum([
                v.get("other", 0),
                v.get("pumpedStorage", 0)
            ])

        return agg
