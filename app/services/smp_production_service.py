from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from io import BytesIO

from fastapi import HTTPException

from app.services.smp_service import SMPService
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
RENEWABLE_KEYS = ["renewableSum", "RenewableSum", "renewable_sum", "renewable"]

# Per client direction (Jun 2026): the SMP chart's Y-axis must publish the
# same total the production-mix pie chart shows — i.e. the sum of all
# generation sources (non-renewables + renewables + other) with NO
# subtraction. Keys mirror what energy_overview_service / pie chart use.
# NOGA's renamed fields are already normalised back to these historical
# names inside ``NogaService._flatten_energy``.
TOTAL_GENERATION_KEYS_FOR_SMP = [
    # Non-renewables
    "coal",
    "natural_Gas", "natural_gas",
    "diesel", "Diesel",
    "mazut",
    "termo_Soler", "solar", "solar_thermal",
    # Renewables
    "photoVoltaic", "photovoltaic", "photo_voltaic",
    "bio_Gas", "biogas",
    "wind",
    "photovoltaicIntegrated", "pv_storage", "photovoltaic_storage",
    "thermo", "Thermo",
    # Other
    "other",
    "pumpedStorage", "pumped_storage",
]


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
    async def _fetch_production_mix_5min(
        start_dt: datetime,
        end_dt: datetime,
        token: str | None,
    ) -> List[Dict]:
        """Fetch production-mix at 5-minute resolution from NOGA (primary)
        with NZO 5-min fallback.

        Do NOT call ``NogaService.fetch_production_mix`` for SMP — it
        returns NZO at *hourly* resolution on the fallback path, where each
        value is the sum of 12 five-minute MW readings (~12× too high).
        That bug zeroed/inflated the SMP chart in an earlier deploy and is
        flagged in _build_total_generation_window_lookup as well.
        """
        from app.services.noga_service import NogaService
        from app.services.noga_source_mode import use_nzo_fallback_only
        from app.services.nzo_fallback_service import NZOFallbackService

        start = to_noga_date(start_dt)
        end = to_noga_date(end_dt)

        async def _nzo_5min() -> List[Dict]:
            return await NZOFallbackService.fetch_energy_data(
                start_date=start,
                end_date=end,
                time_resolution="all",
            )

        if use_nzo_fallback_only():
            return await _nzo_5min()
        try:
            return await NogaService._fetch_from_noga(start, end, token)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "NOGA production-mix failed for SMP, using NZO 5-min: %s", exc
            )
            return await _nzo_5min()

    @staticmethod
    def _build_renewables_window_lookup(
        energy_rows: List[Dict],
        window_minutes: int = 30,
    ) -> Dict[str, float]:
        """Build a {window-anchor: avg renewable MW} lookup from production
        mix rows. Used when the demand payload didn't carry renewables (NOGA
        bare demand endpoint) so we still produce *net* demand for the chart
        instead of silently degrading to gross.
        """
        if window_minutes <= 0:
            raise ValueError("window_minutes must be a positive integer")

        from collections import defaultdict
        from datetime import datetime as _dt

        buckets: Dict[str, list[float]] = defaultdict(list)
        for row in energy_rows or []:
            date_str = row.get("date") or row.get("day") or ""
            time_str = row.get("time") or row.get("hour") or row.get("timestamp")
            try:
                dt = _dt.fromisoformat(_iso_timestamp(date_str, time_str))
            except ValueError:
                continue
            val = next(
                (v for key in RENEWABLE_KEYS if (v := _as_float(row.get(key))) is not None),
                None,
            )
            if val is None:
                continue
            mins = dt.hour * 60 + dt.minute
            anchor_min = (mins // window_minutes) * window_minutes
            anchor = dt.replace(
                hour=anchor_min // 60,
                minute=anchor_min % 60,
                second=0,
                microsecond=0,
            )
            buckets[anchor.isoformat()].append(val)
        return {anchor: sum(vs) / len(vs) for anchor, vs in buckets.items() if vs}

    @staticmethod
    def _build_total_generation_window_lookup(
        energy_rows: List[Dict],
        window_minutes: int = 30,
    ) -> Dict[str, float]:
        """Build a {window-anchor: avg total-generation MW} lookup from
        production-mix rows.

        Total generation = sum of ALL generation categories (non-renewables +
        renewables + other), matching the production-mix pie chart. Per client
        direction (Jun 2026) this — not gross demand and not demand-minus-
        renewables — is what the SMP chart's Y-axis must publish. Do NOT
        re-introduce a subtraction or swap back to DemandService without
        checking the PRD; this field has flipped meaning several times.
        """
        if window_minutes <= 0:
            raise ValueError("window_minutes must be a positive integer")

        from collections import defaultdict
        from datetime import datetime as _dt

        buckets: Dict[str, list[float]] = defaultdict(list)
        for row in energy_rows or []:
            date_str = row.get("date") or row.get("day") or ""
            time_str = row.get("time") or row.get("hour") or row.get("timestamp")
            try:
                dt = _dt.fromisoformat(_iso_timestamp(date_str, time_str))
            except ValueError:
                continue
            total = 0.0
            saw_any = False
            for key in TOTAL_GENERATION_KEYS_FOR_SMP:
                val = _as_float(row.get(key))
                if val is None:
                    continue
                total += val
                saw_any = True
            if not saw_any:
                continue
            mins = dt.hour * 60 + dt.minute
            anchor_min = (mins // window_minutes) * window_minutes
            anchor = dt.replace(
                hour=anchor_min // 60,
                minute=anchor_min % 60,
                second=0,
                microsecond=0,
            )
            buckets[anchor.isoformat()].append(total)
        return {anchor: sum(vs) / len(vs) for anchor, vs in buckets.items() if vs}

    # Each combined_series item represents a 30-min bin (SMP is half-hourly),
    # so MWh per bin = (mean MW for the bin) × 0.5h. Hard-coded because the
    # SMP source resolution is fixed by the gov dashboard contract.
    _BIN_HOURS = 0.5

    @staticmethod
    def _aggregate(series: List[Dict], period: str) -> List[Dict]:
        """
        Aggregate the per-30-min combined_series by day, month, or year.

        IMPORTANT — per client direction (May 2026): each aggregated period
        must publish the **TOTAL MWh of demand for the period**, not the
        mean MW. Prices remain means (they are ₪/MWh rates; averaging is
        the meaningful summary). The conversion is:

            input net_demand (per-bin) = mean MW over a 30-min window
            output net_demand (per period) = SUM(per-bin mean MW) × 0.5h
                                           = total MWh delivered in the period

        For "day" we aggregate directly from the 30-min series; "month" and
        "year" recurse via daily totals so monthly = sum of daily MWh totals
        (same answer as direct sum × 0.5, but keeps the daily total visible
        and ensures price means follow the existing "mean of daily means"
        contract that the FE was built against).

        Do NOT change ``net_demand`` back to a mean without confirming with
        the client first — this is a deliberate semantic change to match
        the gov dashboard's MWh-per-day axis.
        """
        if period in ("month", "year"):
            daily = SMPProductionService._aggregate(series, period="day")
            buckets: Dict[str, Dict[str, float | int]] = {}
            for item in daily:
                period_key = item.get("period")
                if not period_key:
                    continue
                key = period_key[:7] if period == "month" else period_key[:4]
                bucket = buckets.setdefault(
                    key,
                    {
                        "with_sum": 0.0,
                        "without_sum": 0.0,
                        "net_mwh_total": 0.0,  # SUM of daily MWh = period MWh
                        "count_with": 0,
                        "count_without": 0,
                        "has_net": False,
                    },
                )
                if item.get("price_with_constraints") is not None:
                    bucket["with_sum"] += item["price_with_constraints"]  # type: ignore
                    bucket["count_with"] += 1  # type: ignore
                if item.get("price_without_constraints") is not None:
                    bucket["without_sum"] += item["price_without_constraints"]  # type: ignore
                    bucket["count_without"] += 1  # type: ignore
                if item.get("net_demand") is not None:
                    bucket["net_mwh_total"] += item["net_demand"]  # type: ignore  # daily MWh
                    bucket["has_net"] = True  # type: ignore

            aggregated: List[Dict] = []
            for key, values in buckets.items():
                avg_with = values["with_sum"] / values["count_with"] if values["count_with"] else None
                avg_without = values["without_sum"] / values["count_without"] if values["count_without"] else None
                total_net = values["net_mwh_total"] if values["has_net"] else None
                aggregated.append(
                    {
                        "period": key,
                        "avg_smp": avg_with if avg_with is not None else avg_without,
                        "price_with_constraints": avg_with,
                        "price_without_constraints": avg_without,
                        "net_demand": total_net,
                    }
                )
            aggregated.sort(key=lambda x: x["period"])
            return aggregated

        # Day-level aggregation directly from the per-30-min series.
        buckets: Dict[str, Dict[str, float | int]] = {}
        for item in series:
            try:
                dt = datetime.fromisoformat(item["timestamp"])
            except Exception:
                continue
            key = dt.date().isoformat()
            bucket = buckets.setdefault(
                key,
                {
                    "with_sum": 0.0,
                    "without_sum": 0.0,
                    "net_mw_sum": 0.0,  # sum of 30-min mean MW values
                    "count_with": 0,
                    "count_without": 0,
                    "has_net": False,
                },
            )
            if item.get("price_with_constraints") is not None:
                bucket["with_sum"] += item["price_with_constraints"]  # type: ignore
                bucket["count_with"] += 1  # type: ignore
            if item.get("price_without_constraints") is not None:
                bucket["without_sum"] += item["price_without_constraints"]  # type: ignore
                bucket["count_without"] += 1  # type: ignore
            if item.get("net_demand") is not None:
                bucket["net_mw_sum"] += item["net_demand"]  # type: ignore
                bucket["has_net"] = True  # type: ignore

        aggregated: List[Dict] = []
        for key, values in buckets.items():
            avg_with = values["with_sum"] / values["count_with"] if values["count_with"] else None
            avg_without = values["without_sum"] / values["count_without"] if values["count_without"] else None
            # Day TOTAL MWh = sum of 30-min mean MW × 0.5h.
            total_net_mwh = (
                values["net_mw_sum"] * SMPProductionService._BIN_HOURS
                if values["has_net"]
                else None
            )
            aggregated.append(
                {
                    "period": key,
                    "avg_smp": avg_with if avg_with is not None else avg_without,
                    "price_with_constraints": avg_with,
                    "price_without_constraints": avg_without,
                    "net_demand": total_net_mwh,
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
        # Per client direction (Jun 2026): SMP chart's Y-axis publishes the
        # SAME total the production-mix pie chart shows — i.e. sum of all
        # generation categories (non-renewables + renewables + other), no
        # subtraction. Source: NogaService.fetch_production_mix (NOGA-first
        # with NZO fallback). Field renamed upstream — _normalize_noga_sample
        # already mirrors the new NOGA keys back to the historical names that
        # TOTAL_GENERATION_KEYS_FOR_SMP looks up.
        #
        # History to preserve: this field was net (demand − renewables) and
        # earlier was gross demand. Do not flip back without re-reading the
        # PRD and the Jun-2026 client message.
        production_mix = await SMPProductionService._fetch_production_mix_5min(
            start_dt, end_dt, token
        )
        # SMP is half-hourly: each price represents [T, T+30min). Build the
        # total-generation lookup as the *mean* of the underlying 5-min
        # samples in each 30-min window (or the single NZO hourly sample
        # broadcast across two bins when only hourly NZO data is available).
        total_gen_lookup = SMPProductionService._build_total_generation_window_lookup(
            production_mix, window_minutes=30
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
                # ``net_demand`` here = total electricity generation =
                # non_renewables + renewables + other, matching the pie chart.
                # Pulled from the parallel production-mix lookup (NOGA primary,
                # NZO fallback). We deliberately ignore any DEMAND_KEYS the
                # SMP payload may carry — those are gross consumption, not
                # what the client asked for.
                generation_value = total_gen_lookup.get(timestamp)

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

                if generation_value is not None:
                    net_demand_series.append({"timestamp": timestamp, "net_demand": generation_value})

                if smp_value is not None or generation_value is not None:
                    combined_series.append(
                        {
                            "timestamp": timestamp,
                            "smp": smp_value,
                            "price_with_constraints": price_with,
                            "price_without_constraints": price_without,
                            "net_demand": generation_value,
                        }
                    )

                if smp_value is not None and generation_value is not None:
                    correlation.append({"smp": smp_value, "net_demand": generation_value})

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

    @staticmethod
    def to_excel(payload: Dict) -> bytes:
        """
        Export SMP production vs marginal price payload to Excel.
        """
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            summary_rows = [
                {"metric": "start_date", "value": payload.get("start_date")},
                {"metric": "end_date", "value": payload.get("end_date")},
                {"metric": "view", "value": payload.get("view")},
            ]
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

            for sheet_name, key in [
                ("smp_series", "smp_series"),
                ("net_demand_series", "net_demand_series"),
                ("combined_series", "combined_series"),
                ("correlation_day", "correlation"),
                ("correlation_month", payload.get("correlation_by_view", {}).get("month")),
                ("correlation_year", payload.get("correlation_by_view", {}).get("year")),
                ("daily_average", "daily_average"),
                ("monthly_average", "monthly_average"),
                ("yearly_average", "yearly_average"),
            ]:
                data = payload.get(key) if isinstance(key, str) else key
                if data:
                    pd.DataFrame(data).to_excel(writer, sheet_name=sheet_name, index=False)

        buffer.seek(0)
        return buffer.getvalue()
