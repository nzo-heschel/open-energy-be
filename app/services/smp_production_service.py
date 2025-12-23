from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException

from app.services.smp_service import SMPService
from app.services.demand_service import DemandService
from app.utils.date_utils import to_iso_date, to_noga_date

PRICE_WITH_CONSTRAINT_KEYS = [
    "day_Ahead_Constrained_Smp",
    "day_ahead_constrained_smp",
    "real_Time_Constrained_Smp",
    "real_time_constrained_smp",
    "priceWithConstraints",
    "price_with_constraints",
    "pricewithconstraints",
    "marginalPriceWithConstraints",
    "marginalpricewithconstraints",
    "smpWithConstraints",
    "smp_with_constraints",
    "smp",
    "price",
    "marginalPrice",
    "SMP",
]
PRICE_WITHOUT_CONSTRAINT_KEYS = [
    "day_Ahead_Unconstrained_Smp",
    "day_ahead_unconstrained_smp",
    "real_Time_Unconstrained_Smp",
    "real_time_unconstrained_smp",
    "priceWithoutConstraints",
    "price_without_constraints",
    "pricewithoutconstraints",
    "marginalPriceWithoutConstraints",
    "marginalpricewithoutconstraints",
    "smpWithoutConstraints",
    "smp_without_constraints",
    "smp_no_constraints",
]
DEMAND_KEYS = ["actual_Demand", "actualDemand", "demand"]
RENEWABLE_KEYS = ["renewableSum", "renewable_sum", "renewable"]


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_first_float(sample: Dict, keys: List[str], allow_fuzzy: bool = False) -> Optional[float]:
    lowered = {k.lower(): v for k, v in sample.items()}
    for key in keys:
        if key in sample and (val := _as_float(sample.get(key))) is not None:
            return val
        key_lower = key.lower()
        if key_lower in lowered and (val := _as_float(lowered.get(key_lower))) is not None:
            return val

    if not allow_fuzzy:
        return None

    for k, v in sample.items():
        if not isinstance(v, (int, float, str)):
            continue
        k_lower = k.lower()
        if "price" in k_lower or "smp" in k_lower:
            val = _as_float(v)
            if val is not None:
                return val
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
    def _aggregate(series: List[Dict], period: str) -> List[Dict]:
        """
        Aggregate timestamped series by day, month, or year.
        """
        buckets: Dict[str, Dict[str, float | int]] = {}
        for item in series:
            try:
                dt = datetime.fromisoformat(item["timestamp"])
            except Exception:
                continue
            if period == "month":
                key = dt.strftime("%Y-%m")
            elif period == "year":
                key = dt.strftime("%Y")
            else:
                key = dt.date().isoformat()
            bucket = buckets.setdefault(
                key,
                {
                    "with_sum": 0.0,
                    "without_sum": 0.0,
                    "net_sum": 0.0,
                    "count_with": 0,
                    "count_without": 0,
                    "count_net": 0,
                },
            )
            if item.get("price_with_constraints") is not None:
                bucket["with_sum"] += item["price_with_constraints"]  # type: ignore
                bucket["count_with"] += 1  # type: ignore
            if item.get("price_without_constraints") is not None:
                bucket["without_sum"] += item["price_without_constraints"]  # type: ignore
                bucket["count_without"] += 1  # type: ignore
            if item.get("net_demand") is not None:
                bucket["net_sum"] += item["net_demand"]  # type: ignore
                bucket["count_net"] += 1  # type: ignore

        aggregated: List[Dict] = []
        for key, values in buckets.items():
            avg_with = values["with_sum"] / values["count_with"] if values["count_with"] else None
            avg_without = values["without_sum"] / values["count_without"] if values["count_without"] else None
            avg_net = values["net_sum"] / values["count_net"] if values["count_net"] else None
            aggregated.append(
                {
                    "period": key,
                    "avg_smp": avg_with if avg_with is not None else avg_without,
                    "price_with_constraints": avg_with,
                    "price_without_constraints": avg_without,
                    "net_demand": avg_net,
                }
            )
        aggregated.sort(key=lambda x: x["period"])
        return aggregated

    @staticmethod
    async def fetch_and_process(start_dt: datetime, end_dt: datetime, token: str) -> Dict:
        raw_data = await SMPService.fetch_smp_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            token,
        )
        demand_data = await DemandService.fetch_demand_data(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            None,
        )
        demand_lookup = DemandService.to_demand_lookup(demand_data)

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
        daily_sums_with: Dict[str, float] = {}
        daily_sums_without: Dict[str, float] = {}

        for day in days:
            date_str = day.get("date") or day.get("day") or ""
            samples = (
                day.get("productionMixData")
                or day.get("forecastProductionMix")
                or day.get("records")
                or day.get("smpData")
                or day.get("smpdata")
                or []
            )
            for sample in samples:
                time_str = sample.get("time") or sample.get("hour") or sample.get("timestamp")
                timestamp = _iso_timestamp(date_str, time_str)

                price_with = _get_first_float(sample, PRICE_WITH_CONSTRAINT_KEYS, allow_fuzzy=True)
                price_without = _get_first_float(sample, PRICE_WITHOUT_CONSTRAINT_KEYS, allow_fuzzy=True)
                if price_with is None and price_without is not None:
                    price_with = price_without
                if price_without is None and price_with is not None:
                    price_without = price_with
                smp_value = price_with if price_with is not None else price_without
                demand_value = next(
                    (val for key in DEMAND_KEYS if (val := _as_float(sample.get(key))) is not None),
                    None,
                )
                if demand_value is None:
                    demand_value = demand_lookup.get(timestamp)
                renewables_value = next(
                    (val for key in RENEWABLE_KEYS if (val := _as_float(sample.get(key))) is not None),
                    None,
                )
                net_demand = None
                if demand_value is not None:
                    net_demand = demand_value - (renewables_value or 0)

                if price_with is not None or price_without is not None:
                    smp_series.append(
                        {
                            "timestamp": timestamp,
                            "smp": smp_value,
                            "price_with_constraints": price_with,
                            "price_without_constraints": price_without,
                        }
                    )
                if smp_value is not None:
                    day_key = _day_key_iso(date_str)
                    daily_sums[day_key] = daily_sums.get(day_key, 0.0) + smp_value
                if price_with is not None:
                    day_key = _day_key_iso(date_str)
                    daily_sums_with[day_key] = daily_sums_with.get(day_key, 0.0) + price_with
                if price_without is not None:
                    day_key = _day_key_iso(date_str)
                    daily_sums_without[day_key] = daily_sums_without.get(day_key, 0.0) + price_without

                if net_demand is not None:
                    net_demand_series.append({"timestamp": timestamp, "net_demand": net_demand})

                if smp_value is not None or net_demand is not None:
                    combined_series.append(
                        {
                            "timestamp": timestamp,
                            "smp": smp_value,
                            "price_with_constraints": price_with,
                            "price_without_constraints": price_without,
                            "net_demand": net_demand,
                        }
                    )

                if smp_value is not None and net_demand is not None:
                    correlation.append({"smp": smp_value, "net_demand": net_demand})

        if not smp_series:
            raise HTTPException(
                status_code=424,
                detail=(
                    "SMP prices were not returned by the upstream API. "
                    "Verify the SMP endpoint access and try a shorter date range."
                ),
            )

        smp_series.sort(key=lambda x: x["timestamp"])
        net_demand_series.sort(key=lambda x: x["timestamp"])
        combined_series.sort(key=lambda x: x["timestamp"])

        daily_smp = []
        for day in sorted(daily_sums.keys()):
            total = daily_sums[day]
            avg = total / 48 if 48 else 0
            with_total = daily_sums_with.get(day)
            without_total = daily_sums_without.get(day)
            daily_smp.append(
                {
                    "date": day,
                    "daily_smp_avg": avg,
                    "daily_smp_avg_with_constraints": (
                        with_total / 48 if with_total is not None else None
                    ),
                    "daily_smp_avg_without_constraints": (
                        without_total / 48 if without_total is not None else None
                    ),
                }
            )
        daily_smp.sort(key=lambda x: x["date"])

                # Aggregations for day/month/year views (driven by start/end only). Use combined series so net_demand is included.
        daily_view = SMPProductionService._aggregate(combined_series, period="day")
        monthly_view = SMPProductionService._aggregate(combined_series, period="month")
        yearly_view = SMPProductionService._aggregate(combined_series, period="year")

        correlation_by_view = {
            "day": [
                {
                    "timestamp": item["timestamp"],
                    "price_with_constraints": item.get("price_with_constraints"),
                    "price_without_constraints": item.get("price_without_constraints"),
                    "net_demand": item.get("net_demand"),
                }
                for item in combined_series
                if item.get("price_with_constraints") is not None
                or item.get("price_without_constraints") is not None
                or item.get("net_demand") is not None
            ],
            "month": [
                {
                    "period": item["period"],
                    "price_with_constraints": item.get("price_with_constraints"),
                    "price_without_constraints": item.get("price_without_constraints"),
                    "net_demand": item.get("net_demand"),
                }
                for item in monthly_view
            ],
            "year": [
                {
                    "period": item["period"],
                    "price_with_constraints": item.get("price_with_constraints"),
                    "price_without_constraints": item.get("price_without_constraints"),
                    "net_demand": item.get("net_demand"),
                }
                for item in yearly_view
            ],
        }
        days_delta = (end_dt - start_dt).days
        if days_delta <= 1:
            default_view = "day"
        elif days_delta <= 45:
            default_view = "month"
        else:
            default_view = "year"

        return {
            "start_date": to_iso_date(start_dt),
            "end_date": to_iso_date(end_dt),
            "view": default_view,
            "smp_series": smp_series,
            "net_demand_series": net_demand_series,
            "combined_series": combined_series,
            "correlation": correlation_by_view.get("day", []),
            "correlation_by_view": correlation_by_view,
            "daily_average": daily_view,
            "daily_smp": daily_smp,
            "monthly_average": monthly_view,
            "yearly_average": yearly_view,
        }
