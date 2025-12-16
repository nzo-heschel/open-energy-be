import random
from datetime import datetime, timedelta

class NogaMockService:

    @staticmethod
    def get_mock_data(start_date, end_date):
        data = []
        current = start_date

        while current <= end_date:
            for minute in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]:
                time_str = f"{minute:02d}"
                data.append({
                    "date": current.strftime("%d-%m-%Y"),
                    "time": f"{str(minute).zfill(2)}:00",
                    "coal": random.uniform(500, 900),
                    "natural_gas": random.uniform(3000, 6000),
                    "diesel": random.uniform(0, 50),
                    "wind": random.uniform(100, 400),
                    "photovoltaic": random.uniform(0, 200),
                    "biogas": random.uniform(5, 20),
                    "solar_thermal": random.uniform(-1, 5),
                    "photovoltaic_storage": random.uniform(0, 30),
                    "pumped_storage": random.uniform(100, 600),
                    "other": random.uniform(10, 50)
                })
            current += timedelta(days=1)

        return data
