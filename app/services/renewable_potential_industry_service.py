import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from app.services.noga_service import NogaService
from app.services.renewable_mix_service import RENEWABLE_BUCKETS
from app.services.renewable_transition_service import TOTAL_GENERATION_KEYS
from app.utils.date_utils import to_iso_date, to_noga_date


class RenewablePotentialIndustryService:
    """
    Delivery 2 - Row 3:
    Potential renewable energy production by industry type (here: solar, wind, biogas),
    aggregated daily for a selected date range. Calculation: each 5-minute sample (MW) is
    converted to energy (MWh) by dividing by 12, then summed per day.
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
    def _sample_buckets(sample: Dict) -> Tuple[Dict[str, float], float]:
        """
        Convert a single 5-minute power sample to (bucket -> MWh, total MWh).
        """
        buckets: Dict[str, float] = {"solar": 0.0, "wind": 0.0, "other": 0.0}
        for bucket, keys in RENEWABLE_BUCKETS.items():
            buckets[bucket] = sum(sample.get(k, 0) or 0 for k in keys) / 12
        total_mwh = sum(sample.get(key, 0) or 0 for key in TOTAL_GENERATION_KEYS) / 12
        return buckets, total_mwh

    @staticmethod
    def _aggregate_daily(raw: List[Dict], start_dt: datetime, end_dt: datetime) -> Tuple[List[Dict], Dict]:
        daily: Dict[str, Dict[str, float]] = {}

        for sample in raw:
            ts = RenewablePotentialIndustryService._parse_timestamp(sample)
            if not ts:
                continue
            if ts < start_dt or ts > end_dt + timedelta(seconds=59):
                continue

            day_label = ts.strftime("%Y-%m-%d")
            buckets, total_mwh = RenewablePotentialIndustryService._sample_buckets(sample)
            entry = daily.setdefault(
                day_label,
                {"solar": 0.0, "wind": 0.0, "other": 0.0, "total_mwh": 0.0},
            )
            entry["solar"] += buckets["solar"]
            entry["wind"] += buckets["wind"]
            entry["other"] += buckets["other"]
            entry["total_mwh"] += total_mwh

        series: List[Dict] = []
        totals = {"solar": 0.0, "wind": 0.0, "other": 0.0, "total_mwh": 0.0}
        for day_label in sorted(daily.keys()):
            entry = daily[day_label]
            series.append(
                {
                    "date": day_label,
                    "solar_mwh": round(entry["solar"], 2),
                    "wind_mwh": round(entry["wind"], 2),
                    "other_mwh": round(entry["other"], 2),
                    "total_mwh": round(entry["total_mwh"], 2),
                }
            )
            totals["solar"] += entry["solar"]
            totals["wind"] += entry["wind"]
            totals["other"] += entry["other"]
            totals["total_mwh"] += entry["total_mwh"]

        totals = {k: round(v, 2) for k, v in totals.items()}
        return series, totals

    @staticmethod
    async def get_potential(
        start_dt: datetime,
        end_dt: datetime,
        token: str | None = None,
    ) -> Dict:
        """
        Fetch and aggregate daily renewable potential by industry type for the given date range.
        """
        api_token = token or os.getenv("NOGA_API_TOKEN")
        raw = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            api_token,
        )

        series, totals = RenewablePotentialIndustryService._aggregate_daily(raw, start_dt, end_dt)

        return {
            "start_date": to_iso_date(start_dt),
            "end_date": to_iso_date(end_dt),
            "filter": "date_range",
            "series": series,
            "totals": totals,
            "unit": "MWh",
            "y_axis_label": "[MWh]",
            "energy_types": {
                "solar": "Photovoltaic + photovoltaic with storage (MWh). Thermal solar is classified as non-renewable.",
                "wind": "Wind generation (MWh).",
                "other": "Biogas generation (MWh).",
            },
            "tooltip": (
                "Renewable production potential by industry type (solar, wind, biogas). "
                "Each 5-minute NOGA sample (MW) is converted to energy (MWh) by dividing by 12, "
                "then summed for each day of the selected date range."
            ),
            "source": "NOGA renewable generation API (5-minute sampling) with NZO fallback.",
            "data_availability_note": (
                "NOGA/NZO data is available from 2024 onwards. "
                "Data for 2021, 2022, and 2023 is not available in the source."
            ),
        }

    @staticmethod
    def to_excel(series: List[Dict], totals: Dict) -> bytes:
        """
        Build an Excel workbook with totals and daily series.
        """
        import io
        import pandas as pd

        buffer = io.BytesIO()
        df_totals = pd.DataFrame(
            [
                {"Energy Type": "Solar", "MWh": totals.get("solar", 0)},
                {"Energy Type": "Wind", "MWh": totals.get("wind", 0)},
                {"Energy Type": "Other (Biogas)", "MWh": totals.get("other", 0)},
                {"Energy Type": "Total", "MWh": totals.get("total_mwh", 0)},
            ]
        )
        df_series = pd.DataFrame(series)

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_totals.to_excel(writer, sheet_name="Totals", index=False)
            df_series.to_excel(writer, sheet_name="Daily Series", index=False)

        buffer.seek(0)
        return buffer.getvalue()
