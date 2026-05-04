import os
from datetime import datetime, timedelta
from typing import Dict, List

from app.services.noga_service import NogaService
from app.utils.date_utils import parse_date, to_iso_date, to_noga_date
from app.utils.response_formatter import flatten_level2, format_categories


class EnergyOverviewService:

    # --------------------------------------------------------------
    # HOURLY AVERAGING (5-min to 1 hour)
    # --------------------------------------------------------------
    @staticmethod
    def hourly_average(values: List[Dict]) -> List[Dict]:
        """
        Converts 5-min samples to hourly values by summing last hour and dividing by 12.
        """
        grouped = {}

        for v in values:
            hour_key = f"{v['date']} {v['time'][:2]}"
            grouped.setdefault(hour_key, []).append(v)

        result = []

        for hour_key, items in grouped.items():
            hour_entry = {"hour": hour_key}
            for key in items[0].keys():
                if key in ["date", "time"] or key.startswith("_"):
                    continue
                hour_entry[key] = sum(i.get(key, 0) for i in items) / 12
            result.append(hour_entry)

        return result

    # --------------------------------------------------------------
    # HIERARCHY AGGREGATION
    # --------------------------------------------------------------
    @staticmethod
    def aggregate(hourly: List[Dict]) -> Dict:
        """
        Builds new category format (non_renewables, renewables, other)
        """
        level1 = {
            "non_renewables": 0,
            "renewables": 0,
            "other": 0
        }

        level2 = {
            "non_renewables": {
                "coal": 0,
                "natural_gas": 0,
                "diesel": 0,
                "fuel_oil": 0,
            },
            "renewables": {
                "photovoltaic": 0,
                "biogas": 0,
                "wind": 0,
                "solar": 0,
                "pv_storage": 0,
            },
            "other": {
                "other": 0,
                "batteries": 0,
                "pumped_storage": 0,
            }
        }

        def sum_keys(entry: Dict, keys):
            return sum(entry.get(k, 0) for k in keys)

        for h in hourly:
            # Fossil — diesel (Soler/דיזל) and fuel_oil (Mazout/מזוט) are separate
            level2["non_renewables"]["coal"] += sum_keys(h, ["coal"])
            level2["non_renewables"]["natural_gas"] += sum_keys(h, ["natural_Gas", "natural_gas"])
            level2["non_renewables"]["diesel"] += sum_keys(h, ["diesel", "Diesel"])
            level2["non_renewables"]["fuel_oil"] += sum_keys(h, ["mazut"])

            # Renewable — "storage" field dropped per client; batteries moved to Other
            level2["renewables"]["photovoltaic"] += sum_keys(
                h, ["photoVoltaic", "photovoltaic", "photo_voltaic"]
            )
            level2["renewables"]["biogas"] += sum_keys(h, ["bio_Gas", "biogas"])
            level2["renewables"]["wind"] += sum_keys(h, ["wind"])
            level2["renewables"]["solar"] += sum_keys(h, ["termo_Soler", "solar"])
            level2["renewables"]["pv_storage"] += sum_keys(
                h,
                [
                    "photovoltaicIntegrated",
                    "pv_storage",
                    "photovoltaic_storage",
                ],
            )

            # Other — batteries and pumped_storage are distinct standalone fields
            level2["other"]["other"] += sum_keys(h, ["other"])
            level2["other"]["batteries"] += sum_keys(h, ["batteries"])
            level2["other"]["pumped_storage"] += sum_keys(h, ["pumpedStorage", "pumped_storage", "pumpedStorageBattery"])

        # Level-1 sums
        level1["non_renewables"] = sum(level2["non_renewables"].values())
        level1["renewables"] = sum(level2["renewables"].values())
        level1["other"] = sum(level2["other"].values())

        total = sum(level1.values())

        percentages = {
            k: round((v / total) * 100, 2) if total > 0 else 0
            for k, v in level1.items()
        }

        renewable_generation = level1["renewables"]
        renewable_share_percent = round((renewable_generation / total) * 100, 2) if total else 0

        categories = format_categories(flatten_level2(level2))
        category_percentages = {
            cat["category_name"]: round((cat["total_value"] / total) * 100, 2) if total > 0 else 0
            for cat in categories
        }

        return {
            "level1": level1,
            "level2": level2,
            "percentages": percentages,
            "categories": categories,
            "category_percentages": category_percentages,
            "total": total,
            "renewable_generation": renewable_generation,
            "renewable_share_percent": renewable_share_percent,
        }

    # --------------------------------------------------------------
    # MAIN PROCESS ENTRY
    # --------------------------------------------------------------
    @staticmethod
    async def get_overview(start_date: str, end_date: str) -> Dict:

        token = os.getenv("NOGA_API_TOKEN")
        start_dt = parse_date(start_date)
        end_dt = parse_date(end_date).replace(hour=23, minute=59, second=59)

        # Fetch from NOGA API
        raw = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            token,
        )

        # Filter raw to requested window (guard against over-fetch).
        filtered_raw = []
        for v in raw:
            try:
                ts = datetime.strptime(f"{v['date']} {v['time']}", "%d-%m-%Y %H:%M:%S")
            except Exception:
                try:
                    ts = datetime.strptime(f"{v['date']} {v['time']}", "%d-%m-%Y %H:%M")
                except Exception:
                    continue
            if start_dt <= ts <= end_dt + timedelta(seconds=59):
                filtered_raw.append(v)
        raw = filtered_raw

        # Hourly averaging
        hourly = EnergyOverviewService.hourly_average(raw)

        # Aggregation
        result = EnergyOverviewService.aggregate(hourly)

        # Tooltip from Delivery-1 specification
        result["tooltip"] = (
            "The chart shows Israel's electricity generation mix and illustrates the "
            "different energy sources: non-renewables (coal, natural gas, diesel, fuel oil) and "
            "renewables (PV, biogas, wind, solar). Data updated hourly from NOGA."
        )

        result["start_date"] = to_iso_date(start_dt)
        result["end_date"] = to_iso_date(end_dt)

        return result

    # --------------------------------------------------------------
    # EXCEL EXPORT
    # --------------------------------------------------------------
    @staticmethod
    def to_excel_bytes(result: Dict) -> bytes:
        """
        Returns Excel file in memory (xlsx format).
        """
        import pandas as pd
        import io

        buffer = io.BytesIO()

        df_level1 = pd.DataFrame(
            [{"Category": k, "Value": v, "Percentage": result["percentages"][k]}
             for k, v in result["level1"].items()]
        )

        detailed = []
        for cat, subitems in result["level2"].items():
            for sub, val in subitems.items():
                detailed.append({
                    "Category": cat,
                    "Subcategory": sub,
                    "Value": val
                })

        df_level2 = pd.DataFrame(detailed)

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_level1.to_excel(writer, sheet_name="Summary", index=False)
            df_level2.to_excel(writer, sheet_name="Detailed", index=False)

        buffer.seek(0)
        return buffer.getvalue()
