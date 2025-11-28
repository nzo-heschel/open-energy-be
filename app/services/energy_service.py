# app/services/energy_service.py

from app.services.noga_service import NogaService
from datetime import datetime, timedelta

class EnergyService:

    @staticmethod
    async def categorize_energy_data(raw_data):
        """
        Categorize energy data into Fossil, Renewable, and Other energy types.
        """
        categories = {
            "fossil_energy": {"coal": 0, "natural_gas": 0, "diesel": 0},
            "renewable_energy": {"wind": 0, "solar": 0, "biogas": 0, "photovoltaic": 0},
            "other": {"pumped_storage": 0, "other": 0}
        }

        for row in raw_data:
            for energy_type, value in row.items():
                if energy_type == "coal":
                    categories["fossil_energy"]["coal"] += value
                elif energy_type == "natural_gas":
                    categories["fossil_energy"]["natural_gas"] += value
                elif energy_type == "diesel":
                    categories["fossil_energy"]["diesel"] += value
                elif energy_type == "wind":
                    categories["renewable_energy"]["wind"] += value
                elif energy_type == "solar":
                    categories["renewable_energy"]["solar"] += value
                elif energy_type == "biogas":
                    categories["renewable_energy"]["biogas"] += value
                elif energy_type == "photovoltaic":
                    categories["renewable_energy"]["photovoltaic"] += value
                elif energy_type == "pumped_storage":
                    categories["other"]["pumped_storage"] += value
                elif energy_type == "other":
                    categories["other"]["other"] += value

        return categories

    @staticmethod
    async def apply_time_filter(data, period: str):
        """
        Filter data based on the given time period.
        Possible values: 'today', 'this_month', 'this_year', 'this_decade'
        """
        now = datetime.utcnow()

        if period == 'today':
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return [entry for entry in data if datetime.fromisoformat(entry["timestamp"]) >= start_time]

        elif period == 'this_month':
            start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return [entry for entry in data if datetime.fromisoformat(entry["timestamp"]) >= start_time]

        elif period == 'this_year':
            start_time = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return [entry for entry in data if datetime.fromisoformat(entry["timestamp"]) >= start_time]

        elif period == 'this_decade':
            start_time = datetime(now.year - (now.year % 10), 1, 1, 0, 0)
            return [entry for entry in data if datetime.fromisoformat(entry["timestamp"]) >= start_time]

        return data  # default case, return all data if no filter matches

    @staticmethod
    async def get_energy_data(period: str):
        """
        Get energy data categorized into fossil, renewable, and other types, with optional time filters.
        """
        raw_data = await NogaService.calculate_hourly_average()

        # Apply time filtering
        filtered_data = await EnergyService.apply_time_filter(raw_data, period)

        # Categorize the energy data into fossil, renewable, and other
        categorized_data = await EnergyService.categorize_energy_data(filtered_data)

        return categorized_data

    @staticmethod
    async def get_energy_pie_chart_data(period: str):
        """
        Returns data structured for pie chart.
        """
        energy_data = await EnergyService.get_energy_data(period)

        # Preparing for pie chart
        pie_chart_data = {
            "fossil_energy": sum(energy_data["fossil_energy"].values()),
            "renewable_energy": sum(energy_data["renewable_energy"].values()),
            "other": sum(energy_data["other"].values()),
            "details": {
                "fossil_energy": energy_data["fossil_energy"],
                "renewable_energy": energy_data["renewable_energy"],
                "other": energy_data["other"]
            }
        }

        return pie_chart_data
