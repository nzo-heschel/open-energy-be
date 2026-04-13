# app/services/delivery4_forecasts_service.py
"""
Delivery 4 — Diagram 2 only (PRD: תחזיות והשוואות, diagram #2).
Source: _Delivery 4 - NZO Open Energy website.xlsx — sheet "Delivery 4 Diagram 2".
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_XLSX = _PROJECT_ROOT / "_Delivery 4 - NZO Open Energy website.xlsx"


def _workbook_path() -> Path:
    override = os.getenv("DELIVERY4_XLSX_PATH")
    if override:
        return Path(override)
    return _DEFAULT_XLSX


def _slug_region(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "region"


def _read_diagram2_sheet(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, str], Optional[str]]:
    """
    Parse Diagram 2 sheet: data rows, column titles from row 1, optional footnote row.
    """
    df = pd.read_excel(path, sheet_name="Delivery 4 Diagram 2", header=None)

    labels = {
        "solar_share_2025": _cell_str(df, 1, 1) or "2025 Solar Share",
        "renewable_target_2030": _cell_str(df, 1, 2) or "2030 renewable target",
        "renewable_target_2050": _cell_str(df, 1, 3) or "2050 renewable target",
    }

    regions: List[Dict[str, Any]] = []
    footnote: Optional[str] = None

    for r in range(2, len(df)):
        name = df.iloc[r, 0]
        c1 = df.iloc[r, 1]

        if pd.isna(name) or str(name).strip() == "":
            if pd.notna(c1) and len(str(c1).strip()) > 30:
                footnote = str(c1).strip()
            continue

        raw_name = str(name).strip()
        if _is_noise_row(raw_name):
            continue

        solar = df.iloc[r, 1]
        t2030 = df.iloc[r, 2]
        t2050 = df.iloc[r, 3]

        solar_val = float(solar) if pd.notna(solar) else None
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


def _cell_str(df: pd.DataFrame, row: int, col: int) -> Optional[str]:
    v = df.iloc[row, col]
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s else None


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
    """Delivery 4 — Diagram 2 (international comparison) from the NZO workbook."""

    @staticmethod
    def get_international_comparison(
        include_2050_targets: bool = True,
        include_solar_share: bool = True,
    ) -> Dict[str, Any]:
        """
        Diagram #2 — horizontal bars: 2030 target (always), optional 2050 and 2025 solar share.

        Values in the workbook are fractions (0–1), not percent points.
        """
        path = _workbook_path()
        if not path.is_file():
            raise FileNotFoundError(f"Delivery 4 workbook not found: {path}")

        regions_raw, column_labels_from_sheet, footnote = _read_diagram2_sheet(path)
        missing_solar = [r["region"] for r in regions_raw if not r["solar_data_available"]]
        validation = _validation_notes(regions_raw)

        # Strip internal flags from each region in the response; keep clean chart fields.
        regions: List[Dict[str, Any]] = []
        for r in regions_raw:
            entry: Dict[str, Any] = {
                "region": r["region"],
                "region_key": r["region_key"],
                "solar_share_2025": r["solar_share_2025"],
                "renewable_target_2030": r["renewable_target_2030"],
                "renewable_target_2050": r["renewable_target_2050"],
            }
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
                "workbook_path": str(path.resolve()),
                "sheet": "Delivery 4 Diagram 2",
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

        meta_rows = [
            {"key": "diagram_id", "value": payload.get("diagram_id")},
            {"key": "title_en", "value": payload.get("title")},
            {"key": "title_he", "value": payload.get("title_he")},
            {"key": "value_unit", "value": payload.get("value_unit")},
            {"key": "include_2030_targets", "value": True},
            {"key": "include_2050_targets", "value": include_2050},
            {"key": "include_solar_share", "value": include_solar},
            {"key": "source_sheet", "value": (payload.get("source") or {}).get("sheet")},
            {
                "key": "data_refresh_note",
                "value": (payload.get("source") or {}).get("data_refresh_note"),
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
