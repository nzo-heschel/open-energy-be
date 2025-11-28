from datetime import datetime
from typing import Dict, List
from app.services.noga_service import NogaService

class EnergyMixService:
    
    fossil = ["coal", "natural_gas", "diesel"]
    renewables = ["photovoltaic", "biogas", "wind", "solar_thermal", "pv_storage"]
    other = ["pumped_storage", "other"]

    @staticmethod
    def aggregate_raw_data(raw_data: List[Dict]) -> Dict:
        total = 0
        sums = {key: 0 for group in [EnergyMixService.fossil, EnergyMixService.renewables, EnergyMixService.other] for key in group}

        # Sum all hourly values
        for hour in raw_data:
            for key in sums.keys():
                sums[key] += hour[key]
                total += hour[key]

        # First hierarchy (big 3 groups)
        fossil_sum = sum(sums[e] for e in EnergyMixService.fossil)
        renewable_sum = sum(sums[e] for e in EnergyMixService.renewables)
        other_sum = sum(sums[e] for e in EnergyMixService.other)

        return {
            "total_energy": total,
            "hierarchy_1": {
                "fossil": fossil_sum,
                "renewable": renewable_sum,
                "other": other_sum
            },
            "hierarchy_2": {
                "fossil": {e: sums[e] for e in EnergyMixService.fossil},
                "renewable": {e: sums[e] for e in EnergyMixService.renewables},
                "other": {e: sums[e] for e in EnergyMixService.other},
            }
        }

    @staticmethod
    async def get_energy_mix(period: str, start_date=None, end_date=None):

        now = datetime.now()

        if period == "today":
            start = datetime(now.year, now.month, now.day)
            end = now

        elif period == "this_month":
            start = datetime(now.year, now.month, 1)
            end = now

        elif period == "this_year":
            start = datetime(now.year, 1, 1)
            end = now

        elif period == "this_decade":
            start = datetime(now.year - 10, 1, 1)
            end = now

        elif period == "between_dates":
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)

        else:
            raise ValueError("Invalid period")

        # Fetch hourly mock NOGA data
        raw = await NogaService.fetch_raw_data(start, end)

        # Aggregate for pie chart
        return EnergyMixService.aggregate_raw_data(raw)
