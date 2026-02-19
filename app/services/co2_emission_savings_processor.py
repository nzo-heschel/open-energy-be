# app/services/co2_processor.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


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
