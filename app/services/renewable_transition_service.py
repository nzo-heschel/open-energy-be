import os
from datetime import datetime, timedelta
from typing import Dict, List

from app.services.noga_service import NogaService
from app.utils.date_utils import to_iso_date, to_noga_date

# Keys that represent renewable generation in the NOGA response.
RENEWABLE_KEYS = (
    "photoVoltaic",
    "photovoltaic",
    "photovoltaicIntegrated",
    "termo_Soler",
    "solar",
    "solar_thermal",
    "bio_Gas",
    "biogas",
    "wind",
    "pv_storage",
    "photovoltaic_storage",
    "storage",
    "batteries",
)


class RenewableTransitionService:
    """
    Delivery 2 - Row 2:
    Transition to renewable energies in Israel (daily renewable generation totals per selected year).
    """

    @staticmethod
    def _parse_timestamp(sample: Dict) -> datetime | None:
        for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"):
            try:
                return datetime.strptime(f"{sample['date']} {sample['time']}", fmt)
            except Exception:
                continue
        return None

    @staticmethod
    def _sample_energy(sample: Dict) -> tuple[float, float]:
        """
        Convert a single 5-minute power sample to energy (MWh).
        Returns (renewable_mwh, total_mwh).
        """
        renewable_power = sum(sample.get(k, 0) or 0 for k in RENEWABLE_KEYS)
        total_power = 0.0
        for key, value in sample.items():
            if key in ("date", "time"):
                continue
            if isinstance(value, (int, float)):
                total_power += value
        renewable_mwh = renewable_power / 12
        total_mwh = total_power / 12
        return renewable_mwh, total_mwh

    @staticmethod
    def _aggregate_daily(raw: List[Dict], start_dt: datetime, end_dt: datetime) -> tuple[List[Dict], Dict]:
        """
        Aggregate 5-minute samples into daily energy totals (MWh).
        """
        buckets: Dict[str, Dict[str, float]] = {}

        for sample in raw:
            ts = RenewableTransitionService._parse_timestamp(sample)
            if not ts:
                continue
            if ts < start_dt or ts > end_dt + timedelta(seconds=59):
                continue

            day_label = ts.strftime("%Y-%m-%d")
            renewable_mwh, total_mwh = RenewableTransitionService._sample_energy(sample)
            bucket = buckets.setdefault(
                day_label,
                {"renewable_mwh": 0.0, "total_mwh": 0.0},
            )
            bucket["renewable_mwh"] += renewable_mwh
            bucket["total_mwh"] += total_mwh

        series: List[Dict] = []
        totals = {"renewable_mwh": 0.0, "total_mwh": 0.0, "renewable_share_percent": 0.0}

        for day_label in sorted(buckets.keys()):
            bucket = buckets[day_label]
            renewable_mwh = round(bucket["renewable_mwh"], 2)
            total_mwh = round(bucket["total_mwh"], 2)
            share = round((renewable_mwh / total_mwh) * 100, 2) if total_mwh > 0 else 0.0
            series.append(
                {
                    "date": day_label,
                    "renewable_mwh": renewable_mwh,
                    "total_mwh": total_mwh,
                    "renewable_share_percent": share,
                }
            )
            totals["renewable_mwh"] += bucket["renewable_mwh"]
            totals["total_mwh"] += bucket["total_mwh"]

        totals["renewable_share_percent"] = (
            round((totals["renewable_mwh"] / totals["total_mwh"]) * 100, 2)
            if totals["total_mwh"] > 0
            else 0.0
        )
        totals = {k: round(v, 2) if isinstance(v, float) else v for k, v in totals.items()}
        return series, totals

    @staticmethod
    async def get_transition(year: int, token: str | None = None) -> Dict:
        """
        Fetch renewable generation samples for the given year and aggregate daily totals.
        """
        today = datetime.today()
        start_dt = datetime(year=year, month=1, day=1)
        if year == today.year:
            end_dt = today
        else:
            end_dt = datetime(year=year, month=12, day=31, hour=23, minute=59, second=59)

        api_token = token or os.getenv("NOGA_API_TOKEN")
        raw = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            api_token,
        )

        series, totals = RenewableTransitionService._aggregate_daily(raw, start_dt, end_dt)

        return {
            "year": year,
            "start_date": to_iso_date(start_dt),
            "end_date": to_iso_date(end_dt),
            "filter": "year",
            "series": series,
            "totals": totals,
            "tooltip": (
                "Daily renewable generation (MWh) aggregated from NOGA 5-minute samples. "
                "Each 5-minute power reading (MW) is converted to energy by dividing by 12, "
                "then summed for each day to show how renewable output evolves across the selected year."
            )
        }

    @staticmethod
    def to_excel(series: List[Dict], totals: Dict) -> bytes:
        """
        Build an Excel workbook with totals and the daily series.
        """
        import io
        import pandas as pd

        buffer = io.BytesIO()
        df_totals = pd.DataFrame(
            [
                {"Metric": "Renewable energy (MWh)", "Value": totals.get("renewable_mwh", 0)},
                {"Metric": "Total generation (MWh)", "Value": totals.get("total_mwh", 0)},
                {"Metric": "Renewable share (%)", "Value": totals.get("renewable_share_percent", 0)},
            ]
        )
        df_series = pd.DataFrame(series)

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_totals.to_excel(writer, sheet_name="Totals", index=False)
            df_series.to_excel(writer, sheet_name="Daily Series", index=False)

        buffer.seek(0)
        return buffer.getvalue()
