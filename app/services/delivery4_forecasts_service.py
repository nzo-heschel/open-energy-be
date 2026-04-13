# app/services/delivery4_forecasts_service.py
"""
Delivery 4 — Diagram 2 only (PRD: תחזיות והשוואות, diagram #2).

Source data: `data_files/Delivery_4_Diagram_2_International.csv` (not the combined workbook).

Diagram 1 reference data (if used later): `data_files/Delivery_4_Diagram_1_Israel.csv`.
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DIAGRAM2_CSV = _PROJECT_ROOT / "data_files" / "Delivery_4_Diagram_2_International.csv"

# Documented for future diagram-1 endpoints or jobs; not read by this service today.
DIAGRAM1_CSV = _PROJECT_ROOT / "data_files" / "Delivery_4_Diagram_1_Israel.csv"


def _diagram2_csv_path() -> Path:
    override = os.getenv("DELIVERY4_DIAGRAM2_CSV_PATH")
    if override:
        return Path(override)
    return _DEFAULT_DIAGRAM2_CSV


def _slug_region(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "region"


def _read_diagram2_csv(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, str], Optional[str]]:
    """
    Parse Diagram 2 CSV: region rows + optional `_data_refresh_note` row for footnote.
    """
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]

    labels = {
        "solar_share_2025": "2025 Solar Share",
        "renewable_target_2030": "2030 renewable target",
        "renewable_target_2050": "2050 renewable target",
    }

    regions: List[Dict[str, Any]] = []
    footnote: Optional[str] = None

    for _, row in df.iterrows():
        name = row.get("region")
        if pd.isna(name) or str(name).strip() == "":
            continue

        raw_name = str(name).strip()
        if raw_name.startswith("_data_refresh_note") or raw_name == "_data_refresh_note":
            note = row.get("note")
            if pd.notna(note) and str(note).strip():
                footnote = str(note).strip()
            continue

        if _is_noise_row(raw_name):
            continue

        solar = row.get("solar_share_2025")
        t2030 = row.get("renewable_target_2030")
        t2050 = row.get("renewable_target_2050")

        solar_val: Optional[float]
        if pd.isna(solar) or (isinstance(solar, str) and solar.strip() == ""):
            solar_val = None
        else:
            solar_val = float(solar)

        rt30 = float(t2030) if pd.notna(t2030) else None
        rt50 = float(t2050) if pd.notna(t2050) else None

        regions.append(
            {
                "region": raw_name,
                "region_key": _slug_region(raw_name),
                "solar_share_2025": solar_val,
                "renewable_target_2030": rt30,
                "renewable_target_2050": rt50,
                "solar_data_available": solar_val is not None,
            }
        )

    return regions, labels, footnote


def _is_noise_row(name: str) -> bool:
    n = name.lower()
    if "diagram" in n and "#" in name:
        return True
    if len(name) > 60:
        return True
    return False


def _validation_notes(
    regions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    PRD: solar share should be <= renewable share; we compare 2025 solar to 2030 renewable target
    as a sanity check (same order of magnitude for the chart).
    """
    notes: List[Dict[str, Any]] = []
    for row in regions:
        solar = row.get("solar_share_2025")
        rt30 = row.get("renewable_target_2030")
        if solar is None or rt30 is None:
            continue
        if solar > rt30 + 1e-6:
            notes.append(
                {
                    "region": row["region"],
                    "code": "solar_exceeds_renewable_target_2030",
                    "detail": "Solar share (2025) exceeds 2030 renewable electricity target; verify source data.",
                }
            )
    return notes


class Delivery4ForecastsService:
    """Delivery 4 — Diagram 2 (international comparison) from the NZO CSV snapshot."""

    @staticmethod
    def get_international_comparison(
        include_2050_targets: bool = True,
        include_solar_share: bool = True,
    ) -> Dict[str, Any]:
        """
        Diagram #2 — horizontal bars: 2030 target (always), optional 2050 and 2025 solar share.

        Values in the CSV are fractions (0–1), not percent points.
        """
        path = _diagram2_csv_path()
        if not path.is_file():
            raise FileNotFoundError(
                f"Delivery 4 Diagram 2 CSV not found: {path}. "
                "Place data_files/Delivery_4_Diagram_2_International.csv or set DELIVERY4_DIAGRAM2_CSV_PATH."
            )

        regions_raw, column_labels_from_sheet, footnote = _read_diagram2_csv(path)
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
                "region_key": r["region_key"],
                "renewable_target_2030": r["renewable_target_2030"],
            }
            if include_solar_share:
                entry["solar_share_2025"] = r["solar_share_2025"]
            if include_2050_targets:
                entry["renewable_target_2050"] = r["renewable_target_2050"]
            regions.append(entry)

        return {
            "diagram_id": "delivery_4_diagram_2",
            "title": "Renewables — targets vs actual (international comparison)",
            "title_he": "אנרגיות מתחדשות יעדים מול ייצור בפועל",
            "value_unit": "fraction",
            "value_unit_description": "All numeric values are fractions in [0, 1]; multiply by 100 for percent.",
            "filters": {
                "include_2030_targets": True,
                "include_2050_targets": include_2050_targets,
                "include_solar_share": include_solar_share,
            },
            "column_labels": {
                "solar_share_2025": {
                    "en": column_labels_from_sheet.get("solar_share_2025", "2025 Solar Share"),
                    "he": "חלק סולארי (2025)",
                },
                "renewable_target_2030": {
                    "en": column_labels_from_sheet.get("renewable_target_2030", "2030 renewable target"),
                    "he": "יעד אנרגיות מתחדשות 2030",
                },
                "renewable_target_2050": {
                    "en": column_labels_from_sheet.get("renewable_target_2050", "2050 renewable target"),
                    "he": "יעד אנרגיות מתחדשות 2050",
                },
            },
            "regions": regions,
            "regions_without_solar_data": missing_solar,
            "validation": validation,
            "source": {
                "csv_path": str(path.resolve()),
                "diagram_1_csv": str(DIAGRAM1_CSV.resolve()) if DIAGRAM1_CSV.is_file() else None,
                "data_refresh_note": footnote,
            },
            "prd_notes": {
                "filter_2030_mandatory": True,
                "solar_not_published": (
                    "When the solar filter is on, list `regions_without_solar_data` beside the chart "
                    "(PRD: countries without solar data)."
                ),
            },
        }

    @staticmethod
    def to_excel_diagram2(payload: Dict[str, Any]) -> bytes:
        filters = payload.get("filters") or {}
        include_2050 = filters.get("include_2050_targets", True)
        include_solar = filters.get("include_solar_share", True)

        cols = ["region", "region_key"]
        if include_solar:
            cols.append("solar_share_2025")
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
            {
                "key": "data_refresh_note",
                "value": src.get("data_refresh_note"),
            },
        ]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, sheet_name="Diagram 2 data", index=False)
            pd.DataFrame(meta_rows).to_excel(writer, sheet_name="Meta", index=False)
            missing = payload.get("regions_without_solar_data") or []
            if missing:
                pd.DataFrame([{"region": m} for m in missing]).to_excel(
                    writer, sheet_name="No solar data", index=False
                )
        buffer.seek(0)
        return buffer.getvalue()
