# app/services/delivery4_forecasts_service.py
"""
Delivery 4 — Forecasts & comparisons (PRD: תחזיות והשוואות).
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DIAGRAM1_CSV = _PROJECT_ROOT / "data_files" / "diagram_sheet_1.csv"
_DEFAULT_DIAGRAM2_CSV = _PROJECT_ROOT / "data_files" / "diagram_sheet_2.csv"


def _diagram1_csv_path() -> Path:
    override = os.getenv("DELIVERY4_DIAGRAM1_CSV_PATH")
    if override:
        return Path(override)
    return _DEFAULT_DIAGRAM1_CSV


def _diagram2_csv_path() -> Path:
    override = os.getenv("DELIVERY4_DIAGRAM2_CSV_PATH")
    if override:
        return Path(override)
    return _DEFAULT_DIAGRAM2_CSV


def _slug_region(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "region"


def _read_diagram1_csv(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, str], Optional[float]]:
    """
    Parse Diagram 1 CSV (yearly Israel forecast series).
    """
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return [], {}, None

    year_col = df.columns[0]
    # Source sheet contains English labels in row index 1 after pandas uses the
    # first CSV line as column headers.
    english_row = df.iloc[1] if len(df) > 1 else pd.Series(dtype=object)
    columns = list(df.columns)

    renewable_col = columns[1] if len(columns) > 1 else None
    realistic_col = columns[2] if len(columns) > 2 else None
    ministry_col = columns[3] if len(columns) > 3 else None
    nzo_col = columns[4] if len(columns) > 4 else None
    factor_col = columns[-1] if len(columns) > 1 else None

    series_labels = {
        "renewable_rate": str(english_row.get(renewable_col, "Renewable rate")).strip()
        if renewable_col
        else "Renewable rate",
        "realistic_forecast": str(
            english_row.get(realistic_col, "Realistic forecast")
        ).strip()
        if realistic_col
        else "Realistic forecast",
        "ministry_target": str(
            english_row.get(ministry_col, "Ministry of Energy target")
        ).strip()
        if ministry_col
        else "Ministry of Energy target",
        "nzo_target": str(english_row.get(nzo_col, "NZO target")).strip()
        if nzo_col
        else "NZO target",
    }

    realistic_factor: Optional[float] = None
    data_points: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        year_value = row.get(year_col)
        year_text = "" if pd.isna(year_value) else str(year_value).strip()
        if not re.fullmatch(r"\d{4}", year_text):
            continue

        year = int(year_text)
        renewable_rate = float(row.get(renewable_col) or 0) if renewable_col else 0.0
        realistic_forecast = (
            float(row.get(realistic_col) or 0) if realistic_col else 0.0
        )
        ministry_target = float(row.get(ministry_col) or 0) if ministry_col else 0.0
        nzo_target = float(row.get(nzo_col) or 0) if nzo_col else 0.0

        if realistic_factor is None and factor_col:
            maybe_factor = row.get(factor_col)
            if pd.notna(maybe_factor) and str(maybe_factor).strip() != "":
                realistic_factor = float(maybe_factor)

        data_points.append(
            {
                "year": year,
                "renewable_rate": renewable_rate,
                "realistic_forecast": realistic_forecast,
                "ministry_target": ministry_target,
                "nzo_target": nzo_target,
            }
        )

    data_points.sort(key=lambda x: x["year"])
    return data_points, series_labels, realistic_factor


def _read_diagram2_csv(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[str]]:
    """
    Parse Diagram 2 CSV (international comparison).
    """
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return [], {}, []

    columns = list(df.columns)
    # Source sheet contains English labels in row index 0 after pandas uses the
    # first CSV line as column headers.
    label_row = df.iloc[0] if len(df) > 0 else pd.Series(dtype=object)

    region_en_col = columns[0]
    region_he_col = columns[1] if len(columns) > 1 else None
    solar_col = columns[2] if len(columns) > 2 else None
    target_2030_col = columns[3] if len(columns) > 3 else None
    target_2050_col = columns[4] if len(columns) > 4 else None
    source_col = columns[5] if len(columns) > 5 else None

    labels = {
        "solar_share_2024": str(label_row.get(solar_col, "2024 Solar Share")).strip()
        if solar_col
        else "2024 Solar Share",
        "renewable_target_2030": str(
            label_row.get(target_2030_col, "2030 renewable target")
        ).strip()
        if target_2030_col
        else "2030 renewable target",
        "renewable_target_2050": str(
            label_row.get(target_2050_col, "2050 renewable target")
        ).strip()
        if target_2050_col
        else "2050 renewable target",
    }

    regions: List[Dict[str, Any]] = []
    source_notes: List[str] = []

    def _to_float_or_none(value: Any) -> Optional[float]:
        if pd.isna(value) or str(value).strip() == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    for _, row in df.iterrows():
        name = row.get(region_en_col)
        name_text = "" if pd.isna(name) else str(name).strip()
        name_he = row.get(region_he_col) if region_he_col else None
        source_note = row.get(source_col) if source_col else None

        if pd.notna(source_note) and str(source_note).strip():
            source_notes.append(str(source_note).strip())

        if not name_text:
            continue

        if not re.fullmatch(r"[A-Za-z][A-Za-z\s\-()]*", name_text):
            continue
        solar = row.get(solar_col) if solar_col else None
        t2030 = row.get(target_2030_col) if target_2030_col else None
        t2050 = row.get(target_2050_col) if target_2050_col else None

        solar_val = _to_float_or_none(solar)
        rt30 = _to_float_or_none(t2030)
        rt50 = _to_float_or_none(t2050)
        if rt30 is None and rt50 is None:
            # Skip header-like lines such as "English translation".
            continue

        regions.append(
            {
                "region": name_text,
                "region_he": str(name_he).strip() if pd.notna(name_he) else None,
                "region_key": _slug_region(name_text),
                "solar_share_2024": solar_val,
                "renewable_target_2030": rt30,
                "renewable_target_2050": rt50,
                "solar_data_available": solar_val is not None,
            }
        )

    return regions, labels, source_notes


def _validation_notes(
    regions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    PRD: solar share should be <= renewable share; we compare 2024 solar to 2030 renewable target
    as a sanity check (same order of magnitude for the chart).
    """
    notes: List[Dict[str, Any]] = []
    for row in regions:
        solar = row.get("solar_share_2024")
        rt30 = row.get("renewable_target_2030")
        if solar is None or rt30 is None:
            continue
        if solar > rt30 + 1e-6:
            notes.append(
                {
                    "region": row["region"],
                    "code": "solar_exceeds_renewable_target_2030",
                    "detail": "Solar share (2024) exceeds 2030 renewable electricity target; verify source data.",
                }
            )
    return notes


class Delivery4ForecastsService:
    """Delivery 4 — Diagram 1 and Diagram 2 from dedicated CSV snapshots."""

    @staticmethod
    def get_israel_forecast() -> Dict[str, Any]:
        path = _diagram1_csv_path()
        if not path.is_file():
            raise FileNotFoundError(
                f"Delivery 4 Diagram 1 CSV not found: {path}. "
                "Place data_files/diagram_sheet_1.csv or set DELIVERY4_DIAGRAM1_CSV_PATH."
            )

        points, labels, realistic_factor = _read_diagram1_csv(path)
        return {
            "diagram_id": "delivery_4_diagram_1",
            "title": "Renewables forecast trajectory in Israel",
            "title_he": "תחזית שיעור אנרגיות מתחדשות בישראל",
            "value_unit": "fraction",
            "series_labels": labels,
            "data": points,
            "metadata": {
                "year_start": points[0]["year"] if points else None,
                "year_end": points[-1]["year"] if points else None,
                "realistic_forecast_factor": realistic_factor,
            },
            "source": {
                "csv_path": str(path),
                "encoding": "utf-8-sig",
                "source_type": "CSV snapshot",
            },
        }

    @staticmethod
    def get_international_comparison(
        include_2050_targets: bool = True,
        include_solar_share: bool = True,
    ) -> Dict[str, Any]:
        """
        Diagram #2 — horizontal bars: 2030 target (always), optional 2050 and 2024 solar share.

        Values in the CSV are fractions (0–1), not percent points.
        """
        path = _diagram2_csv_path()
        if not path.is_file():
            raise FileNotFoundError(
                f"Delivery 4 Diagram 2 CSV not found: {path}. "
                "Place data_files/diagram_sheet_2.csv or set DELIVERY4_DIAGRAM2_CSV_PATH."
            )

        regions_raw, column_labels_from_sheet, source_notes = _read_diagram2_csv(path)
        missing_solar = (
            [r["region"] for r in regions_raw if not r["solar_data_available"]]
            if include_solar_share
            else []
        )
        validation = _validation_notes(regions_raw) if include_solar_share else []

        regions: List[Dict[str, Any]] = []
        for r in regions_raw:
            entry: Dict[str, Any] = {
                "region": r["region"],
                "region_he": r["region_he"],
                "region_key": r["region_key"],
                "renewable_target_2030": r["renewable_target_2030"],
            }
            if include_solar_share:
                entry["solar_share_2024"] = r["solar_share_2024"]
            if include_2050_targets:
                entry["renewable_target_2050"] = r["renewable_target_2050"]
            regions.append(entry)

        return {
            "diagram_id": "delivery_4_diagram_2",
            "title": "Renewables - targets vs actual (international comparison)",
            "title_he": "אנרגיות מתחדשות יעדים מול ייצור בפועל",
            "value_unit": "fraction",
            "series_labels": column_labels_from_sheet,
            "filters": {
                "include_2030_targets": True,
                "include_2050_targets": include_2050_targets,
                "include_solar_share": include_solar_share,
            },
            "regions": regions,
            "regions_without_solar_data": missing_solar,
            "validation": validation,
            "source": {
                "csv_path": str(path),
                "encoding": "utf-8-sig",
                "source_type": "CSV snapshot",
                "source_notes": source_notes,
            },
        }

    @staticmethod
    def to_excel_diagram2(payload: Dict[str, Any]) -> bytes:
        filters = payload.get("filters") or {}
        include_2050 = filters.get("include_2050_targets", True)
        include_solar = filters.get("include_solar_share", True)

        cols = ["region", "region_key"]
        if include_solar:
            cols.append("solar_share_2024")
        cols.append("renewable_target_2030")
        if include_2050:
            cols.append("renewable_target_2050")

        rows: List[Dict[str, Any]] = []
        for r in payload.get("regions", []):
            row = {k: r.get(k) for k in cols if k in r}
            rows.append(row)

        src = payload.get("source") or {}
        meta_rows = [
            {"key": "diagram_id", "value": payload.get("diagram_id")},
            {"key": "title_en", "value": payload.get("title")},
            {"key": "title_he", "value": payload.get("title_he")},
            {"key": "value_unit", "value": payload.get("value_unit")},
            {"key": "include_2030_targets", "value": True},
            {"key": "include_2050_targets", "value": include_2050},
            {"key": "include_solar_share", "value": include_solar},
            {"key": "source_csv", "value": src.get("csv_path")},
        ]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, sheet_name="Diagram 2 data", index=False)
            pd.DataFrame(meta_rows).to_excel(writer, sheet_name="Meta", index=False)
            source_notes = src.get("source_notes") or []
            if source_notes:
                pd.DataFrame([{"source_note": s} for s in source_notes]).to_excel(
                    writer, sheet_name="Sources", index=False
                )
            missing = payload.get("regions_without_solar_data") or []
            if missing:
                pd.DataFrame([{"region": m} for m in missing]).to_excel(
                    writer, sheet_name="No solar data", index=False
                )
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def to_excel_diagram1(payload: Dict[str, Any]) -> bytes:
        rows = payload.get("data") or []
        metadata = payload.get("metadata") or {}
        src = payload.get("source") or {}
        labels = payload.get("series_labels") or {}

        meta_rows = [
            {"key": "diagram_id", "value": payload.get("diagram_id")},
            {"key": "title_en", "value": payload.get("title")},
            {"key": "title_he", "value": payload.get("title_he")},
            {"key": "value_unit", "value": payload.get("value_unit")},
            {"key": "year_start", "value": metadata.get("year_start")},
            {"key": "year_end", "value": metadata.get("year_end")},
            {
                "key": "realistic_forecast_factor",
                "value": metadata.get("realistic_forecast_factor"),
            },
            {"key": "source_csv", "value": src.get("csv_path")},
        ]

        label_rows = [{"series_key": k, "label": v} for k, v in labels.items()]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, sheet_name="Diagram 1 data", index=False)
            pd.DataFrame(label_rows).to_excel(writer, sheet_name="Series labels", index=False)
            pd.DataFrame(meta_rows).to_excel(writer, sheet_name="Meta", index=False)
        buffer.seek(0)
        return buffer.getvalue()
