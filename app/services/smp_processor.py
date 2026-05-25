# app/services/smp_processor.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from io import BytesIO

# Broadened key detection to better match NOGA SMP payloads.
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
DEMAND_KEYS = ["actual_Demand", "actualDemand", "demand", "netDemand", "net_demand"]
RENEWABLE_KEYS = ["renewableSum", "renewable_sum", "renewable"]


def _iso_timestamp(date_str: str, time_str: str | None) -> str:
    """
    Convert date + time strings from NOGA into ISO 8601.
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
        if key.lower() in lowered and (val := _as_float(lowered.get(key.lower()))) is not None:
            return val

    if not allow_fuzzy:
        return None

    # Fuzzy fallback: any numeric field containing the token as a substring (price/smp)
    for k, v in sample.items():
        if not isinstance(v, (int, float, str)):
            continue
        k_lower = k.lower()
        if "price" in k_lower or "smp" in k_lower:
            val = _as_float(v)
            if val is not None:
                return val
    return None


class SMPProcessor:
    @staticmethod
    def process_smp_data(
        raw_data: List[Dict],
        include_samples: bool,
        demand_lookup: Dict[str, float] | None = None,
        renewables_lookup: Dict[str, float] | None = None,
    ) -> Dict:
        """
        Return SMP price with/without constraints plus net demand averages for charts.

        ``net_demand`` = gross demand minus renewable generation. SMP
        samples don't carry demand or renewables themselves, so both
        come from the windowed lookups the caller built from the
        demand/production-mix payload.
        """
        days: List[Dict] = []
        if isinstance(raw_data, dict):
            days = raw_data.get("energy", raw_data.get("data", [])) or []
        else:
            days = raw_data or []

        flattened = SMPProcessor._flatten(days, demand_lookup or {}, renewables_lookup or {})
        day_avg = SMPProcessor._aggregate(flattened, by="day")
        month_avg = SMPProcessor._aggregate(flattened, by="month")

        payload = {
            "daily_average": day_avg,
            "monthly_average": month_avg,
            "chart_without_constraints": [
                {"timestamp": r["timestamp"], "price": r["price_without_constraints"]}
                for r in flattened
                if r.get("price_without_constraints") is not None
            ],
            "chart_with_constraints": [
                {"timestamp": r["timestamp"], "price": r["price_with_constraints"]}
                for r in flattened
                if r.get("price_with_constraints") is not None
            ],
            "correlation_view": [
                {
                    "timestamp": r["timestamp"],
                    "net_demand": r["net_demand"],
                    "price": r.get("price_with_constraints"),
                }
                for r in flattened
                if r.get("net_demand") is not None and r.get("price_with_constraints") is not None
            ],
        }

        if include_samples:
            payload["samples"] = flattened

        return payload

    @staticmethod
    def _flatten(
        days: List[Dict],
        demand_lookup: Dict[str, float],
        renewables_lookup: Dict[str, float] | None = None,
    ) -> List[Dict]:
        """
        Flatten NOGA daily payload into timestamped samples with price/net demand.

        ``net_demand`` here = demand − renewables (per client direction).
        """
        renewables_lookup = renewables_lookup or {}
        records: List[Dict] = []
        for day in days:
            date_str = day.get("date") or day.get("day") or ""
            samples = (
                day.get("productionMixData")
                or day.get("forecastProductionMix")
                or day.get("records")
                or day.get("smpData")
                or day.get("smpdata")
                or day.get("data")
                or []
            )
            for sample in samples:
                ts = _iso_timestamp(date_str, sample.get("time") or sample.get("hour") or sample.get("timestamp"))

                price_with = _get_first_float(sample, PRICE_WITH_CONSTRAINT_KEYS, allow_fuzzy=True)
                price_without = _get_first_float(sample, PRICE_WITHOUT_CONSTRAINT_KEYS, allow_fuzzy=True)
                # If only one price exists, mirror it so charts are populated.
                if price_with is None and price_without is not None:
                    price_with = price_without
                if price_without is None and price_with is not None:
                    price_without = price_with
                demand_val = _get_first_float(sample, DEMAND_KEYS)
                if demand_val is None:
                    demand_val = demand_lookup.get(ts)
                # Renewables: sample first (rare), then windowed lookup.
                renewables_val = _get_first_float(sample, RENEWABLE_KEYS)
                if renewables_val is None:
                    renewables_val = renewables_lookup.get(ts)
                net_demand = demand_val - (renewables_val or 0) if demand_val is not None else None

                records.append(
                    {
                        "timestamp": ts,
                        "price_with_constraints": price_with,
                        "price_without_constraints": price_without,
                        "net_demand": net_demand,
                        "date": date_str,
                    }
                )
        records.sort(key=lambda x: x["timestamp"])
        return records

    # 30-min bins (SMP source resolution). MWh per bin = mean MW × 0.5h.
    _BIN_HOURS = 0.5

    @staticmethod
    def _aggregate(records: List[Dict], by: str) -> List[Dict]:
        """
        Aggregate by day or month — prices as MEANS, net_demand as TOTAL MWh.

        Per client direction: ``net_demand`` per period is the total MWh of
        demand delivered in that period (not the mean MW). The per-bin input
        is the 30-min mean MW; total period MWh = sum(per-bin MW) × 0.5h.
        Prices stay means (₪/MWh — averaging is the meaningful summary).
        Mirrors the same change in smp_production_service._aggregate.
        """
        if by == "month":
            daily = SMPProcessor._aggregate(records, by="day")
            buckets: Dict[str, Dict[str, float | int]] = {}
            for rec in daily:
                period = rec.get("period")
                if not period:
                    continue
                month_key = period[:7]
                bucket = buckets.setdefault(
                    month_key,
                    {
                        "with_sum": 0.0,
                        "without_sum": 0.0,
                        "net_mwh_total": 0.0,  # SUM of daily MWh = monthly MWh
                        "count_with": 0,
                        "count_without": 0,
                        "has_net": False,
                    },
                )
                if rec.get("price_with_constraints") is not None:
                    bucket["with_sum"] += rec["price_with_constraints"]  # type: ignore
                    bucket["count_with"] += 1  # type: ignore
                if rec.get("price_without_constraints") is not None:
                    bucket["without_sum"] += rec["price_without_constraints"]  # type: ignore
                    bucket["count_without"] += 1  # type: ignore
                if rec.get("net_demand") is not None:
                    bucket["net_mwh_total"] += rec["net_demand"]  # type: ignore
                    bucket["has_net"] = True  # type: ignore

            aggregated: List[Dict] = []
            for bucket_key, values in buckets.items():
                aggregated.append(
                    {
                        "period": bucket_key,
                        "price_with_constraints": (
                            values["with_sum"] / values["count_with"] if values["count_with"] else None
                        ),
                        "price_without_constraints": (
                            values["without_sum"] / values["count_without"] if values["count_without"] else None
                        ),
                        "net_demand": values["net_mwh_total"] if values["has_net"] else None,
                    }
                )

            aggregated.sort(key=lambda x: x["period"])
            return aggregated

        # Day-level aggregation directly from per-30-min records.
        buckets: Dict[str, Dict[str, float | int]] = {}

        for rec in records:
            ts = rec["timestamp"]
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            bucket_key = dt.date().isoformat()
            bucket = buckets.setdefault(
                bucket_key,
                {
                    "with_sum": 0.0,
                    "without_sum": 0.0,
                    "net_mw_sum": 0.0,  # sum of 30-min mean MW
                    "count_with": 0,
                    "count_without": 0,
                    "has_net": False,
                },
            )
            if rec.get("price_with_constraints") is not None:
                bucket["with_sum"] += rec["price_with_constraints"]  # type: ignore
                bucket["count_with"] += 1  # type: ignore
            if rec.get("price_without_constraints") is not None:
                bucket["without_sum"] += rec["price_without_constraints"]  # type: ignore
                bucket["count_without"] += 1  # type: ignore
            if rec.get("net_demand") is not None:
                bucket["net_mw_sum"] += rec["net_demand"]  # type: ignore
                bucket["has_net"] = True  # type: ignore

        aggregated: List[Dict] = []
        for bucket_key, values in buckets.items():
            total_net_mwh = (
                values["net_mw_sum"] * SMPProcessor._BIN_HOURS
                if values["has_net"]
                else None
            )
            aggregated.append(
                {
                    "period": bucket_key,
                    "price_with_constraints": (
                        values["with_sum"] / values["count_with"] if values["count_with"] else None
                    ),
                    "price_without_constraints": (
                        values["without_sum"] / values["count_without"] if values["count_without"] else None
                    ),
                    "net_demand": total_net_mwh,
                }
            )

        aggregated.sort(key=lambda x: x["period"])
        return aggregated


    @staticmethod
    def to_excel(payload: Dict) -> bytes:
        """
        Export SMP payload to Excel with key views.
        """
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            summary_rows = [
                {"metric": "start_date", "value": payload.get("start_date")},
                {"metric": "end_date", "value": payload.get("end_date")},
                {"metric": "view", "value": payload.get("view")},
            ]
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

            for sheet, key in [
                ("chart_with_constraints", "chart_with_constraints"),
                ("chart_without_constraints", "chart_without_constraints"),
                ("correlation", "correlation_view"),
                ("daily_average", "daily_average"),
                ("monthly_average", "monthly_average"),
                ("samples", "samples"),
            ]:
                data = payload.get(key) or []
                if data:
                    pd.DataFrame(data).to_excel(writer, sheet_name=sheet, index=False)
        buffer.seek(0)
        return buffer.getvalue()
