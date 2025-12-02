from datetime import datetime
from typing import Dict, List
from app.services.noga_service import NogaService

class EnergyMixService:

    # New category format
    fossil = ["coal", "natural_gas", "diesel"]
    renewables = ["photovoltaic", "biogas", "wind", "solar"]
    other = ["pumped_storage", "other"]

    @staticmethod
    def aggregate_raw_data(raw_data: List[Dict]) -> Dict:
        total = 0
        sums = {key: 0 for group in [EnergyMixService.fossil, EnergyMixService.renewables, EnergyMixService.other] for key in group}

        # Sum all hourly values
        for hour in raw_data:
            for key in sums.keys():
                sums[key] += hour.get(key, 0)
                total += hour.get(key, 0)

        # First hierarchy (big 3 groups)
        fossil_sum = sum(sums[e] for e in EnergyMixService.fossil)
        renewable_sum = sum(sums[e] for e in EnergyMixService.renewables)
        other_sum = sum(sums[e] for e in EnergyMixService.other)

        return {
            "total_energy": total,
            "hierarchy_1": {
                "fossil_energy": fossil_sum,
                "renewable_energy": renewable_sum,
                "other": other_sum
            },
            "hierarchy_2": {
                "fossil_energy": {e: sums[e] for e in EnergyMixService.fossil},
                "renewable_energy": {e: sums[e] for e in EnergyMixService.renewables},
                "other": {e: sums[e] for e in EnergyMixService.other},
            }
        }

    @staticmethod
    async def get_energy_mix(start_date: str, end_date: str):
        """
        Fetch raw data and aggregate it into new category format between start_date and end_date.
        """
        # Fetch hourly mock NOGA data
        raw = await NogaService.fetch_raw_data(start_date, end_date)

        # Aggregate for pie chart
        return EnergyMixService.aggregate_raw_data(raw)
