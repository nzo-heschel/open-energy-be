import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from app.services.noga_service import NogaService
from app.utils.date_utils import to_iso_date, to_noga_date


# Mapping of renewable buckets to the raw NOGA keys.
RENEWABLE_BUCKETS: Dict[str, Tuple[str, ...]] = {
    "solar": ("photoVoltaic", "photovoltaic", "photovoltaicIntegrated", "termo_Soler", "solar"),
    "wind": ("wind",),
    "other": ("bio_Gas", "biogas"),
}


class RenewableMixService:
    """
    Delivery 2 - Row 1:
    Renewable energy production mix (solar, wind, biogas) aggregated over time.
    """

    @staticmethod
    def _infer_view(start_dt: datetime, end_dt: datetime) -> str:
        days = (end_dt - start_dt).days
        if days <= 1:
            return "day"
        if days <= 31:
            return "month"
        return "year"

    @staticmethod
    def _parse_timestamp(sample: Dict) -> datetime | None:
        """
        Parse NOGA date/time fields into a datetime. Returns None on failure.
        """
        for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"):
            try:
                return datetime.strptime(f"{sample['date']} {sample['time']}", fmt)
            except Exception:
                continue
        return None

    @staticmethod
    def _bucket_key(ts: datetime, view: str) -> Tuple[datetime, str]:
        """
        Return (sort_key, label) for the chosen view.
        """
        if view == "day":
            sort_key = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            label = sort_key.strftime("%Y-%m-%d")
        elif view == "month":
            sort_key = ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            label = sort_key.strftime("%Y-%m")
        else:
            sort_key = ts.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            label = sort_key.strftime("%Y")
        return sort_key, label

    @staticmethod
    def _sample_energy(sample: Dict, category_filter: str | None = None) -> Dict[str, float]:
        """
        Convert a single 5-minute sample into energy buckets (MWh) by dividing by 12.
        """
        buckets = {"solar": 0.0, "wind": 0.0, "other": 0.0}
        for bucket, keys in RENEWABLE_BUCKETS.items():
            buckets[bucket] = sum(sample.get(k, 0) or 0 for k in keys) / 12
        if category_filter:
            # Zero-out non-selected buckets when filtering.
            for k in list(buckets.keys()):
                if k != category_filter:
                    buckets[k] = 0.0
        buckets["total"] = buckets["solar"] + buckets["wind"] + buckets["other"]
        return buckets

    @staticmethod
    def _aggregate_samples(
        raw: List[Dict],
        start_dt: datetime,
        end_dt: datetime,
        view: str,
        category_filter: str | None = None,
    ) -> Tuple[List[Dict], Dict]:
        """
        Filter raw samples to the requested window and aggregate into the requested buckets.
        Returns (series, totals).
        """
        buckets: Dict[str, Dict] = {}

        for sample in raw:
            ts = RenewableMixService._parse_timestamp(sample)
            if not ts:
                continue
            if ts < start_dt or ts > end_dt + timedelta(seconds=59):
                continue

            sort_key, label = RenewableMixService._bucket_key(ts, view)
            energy = RenewableMixService._sample_energy(sample, category_filter)

            if label not in buckets:
                buckets[label] = {
                    "solar": 0.0,
                    "wind": 0.0,
                    "other": 0.0,
                    "total": 0.0,
                    "_sort_key": sort_key,
                }

            bucket = buckets[label]
            bucket["solar"] += energy["solar"]
            bucket["wind"] += energy["wind"]
            bucket["other"] += energy["other"]
            bucket["total"] += energy["total"]

        ordered = sorted(buckets.values(), key=lambda b: b["_sort_key"])
        series: List[Dict] = []
        totals = {"solar": 0.0, "wind": 0.0, "other": 0.0, "total": 0.0}

        for bucket in ordered:
            series.append(
                {
                    "period": bucket["_sort_key"].strftime("%Y-%m-%d")
                    if view == "day"
                    else bucket["_sort_key"].strftime("%Y-%m")
                    if view == "month"
                    else bucket["_sort_key"].strftime("%Y"),
                    "solar_mwh": round(bucket["solar"], 2),
                    "wind_mwh": round(bucket["wind"], 2),
                    "other_mwh": round(bucket["other"], 2),
                    "total_mwh": round(bucket["total"], 2),
                }
            )
            totals["solar"] += bucket["solar"]
            totals["wind"] += bucket["wind"]
            totals["other"] += bucket["other"]
            totals["total"] += bucket["total"]

        totals = {k: round(v, 2) for k, v in totals.items()}
        return series, totals

    @staticmethod
    async def get_mix(
        start_dt: datetime,
        end_dt: datetime,
        token: str | None = None,
        category_filter: str | None = None,
    ) -> Dict:
        """
        Fetch renewable generation samples from NOGA and aggregate them into daily/monthly/yearly buckets.
        """
        api_token = token or os.getenv("NOGA_API_TOKEN")
        view = RenewableMixService._infer_view(start_dt, end_dt)

        raw = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            api_token,
        )

        series, totals = RenewableMixService._aggregate_samples(
            raw,
            start_dt,
            end_dt,
            view,
            category_filter=category_filter,
        )

        return {
            "start_date": to_iso_date(start_dt),
            "end_date": to_iso_date(end_dt),
            "filter": view,
            "category_filter": category_filter,
            "series": series,
            "totals": totals,
            "energy_types": {
                "solar": "Photovoltaic + solar-thermal + photovoltaic with storage (MWh).",
                "wind": "Wind generation (MWh).",
                "other": "Biogas generation (MWh).",
            },
            "tooltip": (
                "Renewable energy production mix showing solar, wind, and biogas generation. "
                "Values are converted from 5-minute samples (MW) to energy (MWh) by dividing each sample by 12, "
                "then summing by day, month, or year depending on the selected filter."
            )
        }

    @staticmethod
    def to_excel(series: List[Dict], totals: Dict) -> bytes:
        """
        Build an Excel workbook with totals and the aggregated series.
        """
        import io
        import pandas as pd

        buffer = io.BytesIO()
        df_totals = pd.DataFrame(
            [
                {"Energy Type": "Solar", "MWh": totals.get("solar", 0)},
                {"Energy Type": "Wind", "MWh": totals.get("wind", 0)},
                {"Energy Type": "Other (Biogas)", "MWh": totals.get("other", 0)},
                {"Energy Type": "Total", "MWh": totals.get("total", 0)},
            ]
        )
        df_series = pd.DataFrame(series)

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_totals.to_excel(writer, sheet_name="Totals", index=False)
            df_series.to_excel(writer, sheet_name="Series", index=False)

        buffer.seek(0)
        return buffer.getvalue()
