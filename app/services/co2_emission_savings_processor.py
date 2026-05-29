# app/services/co2_processor.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


FOSSIL_EMISSION_FIELDS = {
    "coal": "co2_coal",
    "fuel_oil": "co2_fuel_oil",
    "natural_gas": "co2_gas",
    "diesel": "co2_diesel",
    "methanol": "co2_methanol",
}


class CO2Processor:
    @staticmethod
    def _as_float(v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if not s:
                return None
            try:
                return float(s)
            except Exception:
                return None
        return None

    @staticmethod
    def available_keys(samples: List[Dict], max_keys: int = 60) -> List[str]:
        if not samples:
            return []
        keys = list(samples[0].keys())
        return keys[:max_keys]

    @staticmethod
    def sum_samples_divide_by_12(samples: List[Dict], field: str) -> float:
        total = 0.0
        for row in samples:
            val = CO2Processor._as_float(row.get(field))
            if val is not None:
                total += val
        # Data sampled every 5 min → 12 samples/hour → divide by 12
        return total / 12.0

    @staticmethod
    def sum_first_matching_field(samples: List[Dict], candidate_fields: Iterable[str]) -> Tuple[str, float]:
        if not samples:
            raise ValueError("No CO2 samples returned for the selected period.")

        sample0 = samples[0]
        for field in candidate_fields:
            if field in sample0:
                return field, CO2Processor.sum_samples_divide_by_12(samples, field)

        raise ValueError(
            "None of the candidate fields were found in CO2 payload. "
            f"Candidates={list(candidate_fields)} AvailableKeys={list(sample0.keys())}"
        )

    @staticmethod
    def aggregate_totals(samples: List[Dict]) -> Dict:
        """
        Aggregate CO2 samples into period totals.

        NZO/NOGA values are rates for 5-minute samples. Summing a field and
        dividing by 12 converts the sampled rates into tons CO2 or MWh for
        the selected period.

        The emissions ratio is computed with the /12 applied LAST per client
        spec: sum(fossil emissions) / sum(current demand), then /12.
        """
        components = {
            label: CO2Processor.sum_samples_divide_by_12(samples, field)
            for label, field in FOSSIL_EMISSION_FIELDS.items()
        }
        total_emissions = sum(components.values())
        demand_mwh = CO2Processor.sum_samples_divide_by_12(samples, "co2_current_demand")
        renewable_savings = CO2Processor.sum_samples_divide_by_12(samples, "co2_renewables")

        # Ratio: keep raw 5-min sums, divide them, then apply /12 as the last step.
        raw_fossil_sum = sum(
            CO2Processor._as_float(row.get(field)) or 0.0
            for row in samples
            for field in FOSSIL_EMISSION_FIELDS.values()
        )
        raw_demand_sum = sum(
            CO2Processor._as_float(row.get("co2_current_demand")) or 0.0
            for row in samples
        )
        emissions_ratio = (
            (raw_fossil_sum / raw_demand_sum) / 12.0 if raw_demand_sum > 0 else 0.0
        )
        emissions_per_kwh = total_emissions / (demand_mwh * 1000.0) if demand_mwh > 0 else 0.0
        # Renewable savings as a percentage of fossil emissions, per client
        # spec: renewables_CO2 / fossil_CO2 × 100. (Previously the
        # denominator was fossil + savings, which under-reported the figure
        # — e.g. Apr 29 showed 22.21% instead of the expected 28.55%.)
        # Can exceed 100% on high-renewable days, which is expected.
        savings_percent = (
            renewable_savings / total_emissions * 100.0
            if total_emissions > 0
            else 0.0
        )
        # Average fossil emission RATE in mTCO2/h. Each raw sample is already
        # an instantaneous tons-CO2/h rate, so the mean of the samples is the
        # average hourly rate over the period. This backs the "שיעור פליטות
        # CO2 ממקורות פוסיליים" (fossil emission rate) infographic, whose
        # unit is mTCO2/h — NOT the period total.
        sample_count = len(samples) if samples else 0
        fossil_emissions_rate = raw_fossil_sum / sample_count if sample_count else 0.0

        return {
            "components": components,
            "total_emissions": total_emissions,
            "fossil_emissions_rate": fossil_emissions_rate,
            "generation_mwh": demand_mwh,
            "renewable_savings": renewable_savings,
            "emissions_ratio": emissions_ratio,
            "emissions_per_kwh": emissions_per_kwh,
            "renewable_savings_percent": savings_percent,
        }

    @staticmethod
    def hierarchy_from_totals(totals: Dict) -> Dict:
        components = totals.get("components") or {}
        total_emissions = totals.get("total_emissions") or 0.0
        renewable_savings = totals.get("renewable_savings") or 0.0
        return {
            "level1": {
                "fossil_emissions": round(total_emissions, 2),
                "renewable_emissions_savings": round(renewable_savings, 2),
            },
            "level2": {
                "fossil_emissions": {
                    key: round(value, 2)
                    for key, value in components.items()
                },
                "renewable_emissions_savings": {
                    "renewables": round(renewable_savings, 2),
                },
            },
        }
