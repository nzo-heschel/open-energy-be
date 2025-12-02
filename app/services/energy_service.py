from datetime import datetime
from app.services.noga_service import NogaService

class EnergyService:

    @staticmethod
    async def categorize_energy_data(raw_data):
        """
        Categorize energy data into Fossil, Renewable, and Other energy types using new format.
        """
        categories = {
            "fossil_energy": {"coal": 0, "natural_gas": 0, "diesel": 0},
            "renewable_energy": {"photovoltaic": 0, "biogas": 0, "wind": 0, "solar": 0},
            "other": {"pumped_storage": 0, "other": 0}
        }

        for row in raw_data:
            for energy_type, value in row.items():
                if energy_type in categories["fossil_energy"]:
                    categories["fossil_energy"][energy_type] += value
                elif energy_type in categories["renewable_energy"]:
                    categories["renewable_energy"][energy_type] += value
                elif energy_type in categories["other"]:
                    categories["other"][energy_type] += value

        return categories

    @staticmethod
    async def apply_time_filter(data, start_date: str, end_date: str):
        """
        Filter data between start_date and end_date (inclusive).
        """
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        filtered = [
            entry for entry in data
            if start_dt <= datetime.fromisoformat(entry["timestamp"]) <= end_dt
        ]

        return filtered

    @staticmethod
    async def get_energy_data(start_date: str, end_date: str):
        """
        Get energy data categorized into fossil, renewable, and other types.
        """
        # Fetch raw hourly averages
        raw_data = await NogaService.calculate_hourly_average()

        # Apply the new time filter
        filtered_data = await EnergyService.apply_time_filter(raw_data, start_date, end_date)

        # Categorize the energy data
        categorized_data = await EnergyService.categorize_energy_data(filtered_data)

        return categorized_data

    @staticmethod
    async def get_energy_pie_chart_data(start_date: str, end_date: str):
        """
        Returns data structured for pie chart using new categories format.
        """
        energy_data = await EnergyService.get_energy_data(start_date, end_date)

        # Preparing for pie chart
        pie_chart_data = {
            "fossil_energy": sum(energy_data["fossil_energy"].values()),
            "renewable_energy": sum(energy_data["renewable_energy"].values()),
            "other": sum(energy_data["other"].values()),
            "details": energy_data
        }

        return pie_chart_data
