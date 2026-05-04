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
)

TOTAL_GENERATION_KEYS = (
    "coal",
    "natural_Gas",
    "natural_gas",
    "mazut",
    "diesel",
    "Diesel",
    *RENEWABLE_KEYS,
    "other",
    "batteries",
    "pumpedStorage",
    "pumped_storage",
    "pumpedStorageBattery",
)


class RenewableTransitionService:
    """
    Delivery 2 - Row 2:
    Transition to renewable energies in Israel.
    Shows monthly renewable share (%) per year, with all years overlaid.
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
        total_power = sum(sample.get(k, 0) or 0 for k in TOTAL_GENERATION_KEYS)
        renewable_mwh = renewable_power / 12
        total_mwh = total_power / 12
        return renewable_mwh, total_mwh

    @staticmethod
    def _aggregate_monthly(raw: List[Dict], start_dt: datetime, end_dt: datetime) -> tuple[List[Dict], Dict]:
        """
        Aggregate 5-minute samples into monthly energy totals (MWh) and share (%).
        Returns (series, totals).
        """
        buckets: Dict[str, Dict[str, float]] = {}

        for sample in raw:
            ts = RenewableTransitionService._parse_timestamp(sample)
            if not ts:
                continue
            if ts < start_dt or ts > end_dt + timedelta(seconds=59):
                continue

            month_label = ts.strftime("%Y-%m")
            renewable_mwh, total_mwh = RenewableTransitionService._sample_energy(sample)
            bucket = buckets.setdefault(
                month_label,
                {"renewable_mwh": 0.0, "total_mwh": 0.0},
            )
            bucket["renewable_mwh"] += renewable_mwh
            bucket["total_mwh"] += total_mwh

        series: List[Dict] = []
        totals = {"renewable_mwh": 0.0, "total_mwh": 0.0, "renewable_share_percent": 0.0}

        for month_label in sorted(buckets.keys()):
            bucket = buckets[month_label]
            renewable_mwh = round(bucket["renewable_mwh"], 2)
            total_mwh = round(bucket["total_mwh"], 2)
            share = round((renewable_mwh / total_mwh) * 100, 2) if total_mwh > 0 else 0.0
            year = int(month_label[:4])
            month_num = int(month_label[5:])

            series.append(
                {
                    "period": month_label,
                    "year": year,
                    "month": month_num,
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
    async def get_transition(
        start_date: str | None = None,
        end_date: str | None = None,
        years: List[int] | None = None,
        token: str | None = None,
    ) -> Dict:
        """
        Fetch renewable generation and compute monthly renewable share (%).
        Supports multi-year range with per-month breakdown for chart overlay by year.

        Args:
            start_date: ISO date string (YYYY-MM-DD). If not provided, defaults based on years.
            end_date: ISO date string (YYYY-MM-DD). If not provided, defaults to today.
            years: Optional list of years to include.
            token: NOGA API token override.
        """
        today = datetime.today()
        api_token = token or os.getenv("NOGA_API_TOKEN")

        # Determine date range
        if start_date and end_date:
            from app.utils.date_utils import parse_date
            start_dt = parse_date(start_date)
            end_dt = parse_date(end_date).replace(hour=23, minute=59, second=59)
        elif years:
            start_dt = datetime(year=min(years), month=1, day=1)
            end_year = max(years)
            if end_year == today.year:
                end_dt = today
            else:
                end_dt = datetime(year=end_year, month=12, day=31, hour=23, minute=59, second=59)
        else:
            # Default: current year
            start_dt = datetime(year=today.year, month=1, day=1)
            end_dt = today

        raw = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            api_token,
        )

        # Monthly aggregation for the bar chart
        monthly_series, totals = RenewableTransitionService._aggregate_monthly(raw, start_dt, end_dt)

        # Daily aggregation for detailed view
        daily_series, _ = RenewableTransitionService._aggregate_daily(raw, start_dt, end_dt)

        # Extract available years from the data
        available_years = sorted(set(item["year"] for item in monthly_series))

        # Build per-year monthly data for chart overlay (Issue #3, #8)
        # Each year gets its own series with months 1-12
        years_data: Dict[int, List[Dict]] = {}
        for item in monthly_series:
            year = item["year"]
            if year not in years_data:
                years_data[year] = []
            years_data[year].append({
                "month": item["month"],
                "period": item["period"],
                "renewable_share_percent": item["renewable_share_percent"],
                "renewable_mwh": item["renewable_mwh"],
                "total_mwh": item["total_mwh"],
            })

        return {
            "start_date": to_iso_date(start_dt),
            "end_date": to_iso_date(end_dt),
            "filter": "multi_year",
            "available_years": available_years,
            "monthly_series": monthly_series,
            "daily_series": daily_series,
            "years_data": years_data,
            "totals": totals,
            "unit": "[%]",
            "y_axis_label": "[%]",
            "tooltip": (
                "Monthly renewable generation share (%) aggregated from NOGA 5-minute samples. "
                "Each 5-minute power reading (MW) is converted to energy by dividing by 12, "
                "then summed per month. The renewable share is the ratio of renewable MWh "
                "to total MWh for each month."
            ),
            "data_availability_note": (
                "NOGA/NZO data is available from 2024 onwards. "
                "Data for 2021, 2022, and 2023 is not available in the source."
            ),
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
            df_series.to_excel(writer, sheet_name="Monthly Series", index=False)

        buffer.seek(0)
        return buffer.getvalue()
