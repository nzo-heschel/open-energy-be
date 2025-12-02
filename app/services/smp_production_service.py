from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from app.services.smp_service import SMPService
from app.utils.date_utils import to_iso_date, to_noga_date

SMP_KEYS = ["smp", "SMP", "marginalPrice", "price", "priceWithConstraints"]
DEMAND_KEYS = ["actual_Demand", "actualDemand", "demand"]
RENEWABLE_KEYS = ["renewableSum", "renewable_sum", "renewable"]


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_timestamp(date_str: str, time_str: str | None) -> str:
    """
    Convert date + time strings from NOGA into an ISO 8601 timestamp string.
    Falls back to concatenation if parsing fails.
    """
    time_str = time_str or "00:00"
    candidates = [
        ("%d-%m-%Y %H:%M:%S", f"{date_str} {time_str}"),
        ("%d-%m-%Y %H:%M", f"{date_str} {time_str}"),
        ("%Y-%m-%d %H:%M:%S", f"{date_str} {time_str}"),
        ("%Y-%m-%d %H:%M", f"{date_str} {time_str}"),
    ]
    for fmt, value in candidates:
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            continue
    return f"{date_str}T{time_str}"


def _day_key_iso(date_str: str) -> str:
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return to_iso_date(datetime.strptime(date_str, fmt))
        except ValueError:
            continue
    return date_str


class SMPProductionService:
    @staticmethod
    async def fetch_and_process(start_dt: datetime, end_dt: datetime, token: str) -> Dict:
        raw_data = await SMPService.fetch_smp_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            token,
        )

        days: List[Dict] = []
        if isinstance(raw_data, dict):
            days = raw_data.get("energy", raw_data.get("data", [])) or []
        else:
            days = raw_data or []

        smp_series: List[Dict] = []
        net_demand_series: List[Dict] = []
        combined_series: List[Dict] = []
        correlation: List[Dict] = []
        daily_sums: Dict[str, float] = {}

        for day in days:
            date_str = day.get("date") or day.get("day") or ""
            samples = (
                day.get("productionMixData")
                or day.get("forecastProductionMix")
                or day.get("records")
                or []
            )
            for sample in samples:
                time_str = sample.get("time") or sample.get("hour") or sample.get("timestamp")
                timestamp = _iso_timestamp(date_str, time_str)

                smp_value = next(
                    (val for key in SMP_KEYS if (val := _as_float(sample.get(key))) is not None),
                    None,
                )
                demand_value = next(
                    (val for key in DEMAND_KEYS if (val := _as_float(sample.get(key))) is not None),
                    None,
                )
                renewables_value = next(
                    (val for key in RENEWABLE_KEYS if (val := _as_float(sample.get(key))) is not None),
                    None,
                )
                net_demand = None
                if demand_value is not None:
                    net_demand = demand_value - (renewables_value or 0)

                if smp_value is not None:
                    smp_series.append({"timestamp": timestamp, "smp": smp_value})
                    day_key = _day_key_iso(date_str)
                    daily_sums[day_key] = daily_sums.get(day_key, 0.0) + smp_value

                if net_demand is not None:
                    net_demand_series.append({"timestamp": timestamp, "net_demand": net_demand})

                if smp_value is not None or net_demand is not None:
                    combined_series.append(
                        {
                            "timestamp": timestamp,
                            "smp": smp_value,
                            "net_demand": net_demand,
                        }
                    )

                if smp_value is not None and net_demand is not None:
                    correlation.append({"smp": smp_value, "net_demand": net_demand})

        smp_series.sort(key=lambda x: x["timestamp"])
        net_demand_series.sort(key=lambda x: x["timestamp"])
        combined_series.sort(key=lambda x: x["timestamp"])

        daily_smp = []
        for day, total in daily_sums.items():
            avg = total / 48 if 48 else 0
            daily_smp.append({"date": day, "daily_smp_avg": avg})
        daily_smp.sort(key=lambda x: x["date"])

        return {
            "start_date": to_iso_date(start_dt),
            "end_date": to_iso_date(end_dt),
            "smp_series": smp_series,
            "net_demand_series": net_demand_series,
            "combined_series": combined_series,
            "correlation": correlation,
            "daily_smp": daily_smp,
        }
