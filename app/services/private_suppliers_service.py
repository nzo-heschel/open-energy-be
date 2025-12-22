from __future__ import annotations

import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.utils.date_utils import parse_date, to_iso_date
from app.utils.enums import DataFileSource
from app.services.data_file_manager import ensure_fresh_data_file

DEFAULT_CSV_PATH = Path(os.getenv("PRIVATE_SUPPLIERS_CSV_PATH", "Files_Netunei_hashmal_mp_niyud.csv"))


@dataclass
class PrivateSupplierRecord:
    month: str
    total_consumers: float
    new_additions: float


class PrivateSuppliersService:
    @staticmethod
    def _load_dataframe(csv_path: Optional[Path] = None) -> pd.DataFrame:
        csv_path = csv_path or ensure_fresh_data_file(DataFileSource.PRIVATE_SUPPLIERS)

        df: Optional[pd.DataFrame] = None
        last_err: Optional[Exception] = None
        if csv_path.suffix.lower() in (".xls", ".xlsx"):
            try:
                df = pd.read_excel(csv_path)
            except Exception as exc:
                last_err = exc
        else:
            for enc in ("cp1255", "windows-1255", "latin1"):
                try:
                    df = pd.read_csv(csv_path, encoding=enc)
                    break
                except Exception as exc:
                    last_err = exc
        if df is None:
            raise last_err or ValueError("Unable to load CSV")

        # Normalize header text to avoid BOM/whitespace mismatches.
        df.columns = [col.replace("\ufeff", "").strip() for col in df.columns]

        # Resolve column names even if slightly different in the source.
        def normalize_col(value: str) -> str:
            text = str(value or "").strip().lower()
            text = text.replace("\ufeff", "").replace("\u00a0", " ")
            return re.sub(r"[\s/._-]+", "", text)

        normalized_cols = {normalize_col(col): col for col in df.columns}

        def resolve_column(possible: list[str], required: bool = True) -> Optional[str]:
            for name in possible:
                if name in df.columns:
                    return name
            for name in possible:
                normalized = normalize_col(name)
                if normalized in normalized_cols:
                    return normalized_cols[normalized]
            for col in df.columns:
                col_norm = normalize_col(col)
                for name in possible:
                    name_norm = normalize_col(name)
                    if name_norm and name_norm in col_norm:
                        return col
            if not required:
                return None
            return None

        year_month_candidates = [
            "\u05e9\u05e0\u05d4/ \u05d7\u05d5\u05d3\u05e9",
            "\u05e9\u05e0\u05d4/\u05d7\u05d5\u05d3\u05e9",
            "\u05e9\u05e0\u05d4 / \u05d7\u05d5\u05d3\u05e9",
            "\u05e9\u05e0\u05d4/\u00a0\u05d7\u05d5\u05d3\u05e9",
            "year/month",
            "year_month",
            "year month",
            "month",
        ]
        year_month_col = resolve_column(year_month_candidates)
        if year_month_col is None:
            best_col = None
            best_count = 0
            for col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce", format="%Y/%m")
                if parsed.notna().sum() == 0:
                    parsed = pd.to_datetime(df[col], errors="coerce", format="%Y-%m")
                count = parsed.notna().sum()
                if count > best_count:
                    best_col = col
                    best_count = count
            if best_col:
                year_month_col = best_col
            else:
                raise KeyError("Missing expected date column (year/month).")

        total_col = resolve_column(
            [
                "\u05de\u05e1\u05e4\u05e8 \u05d1\u05e7\u05e9\u05d5\u05ea",
                "\u05e1\u05d4\"\u05db \u05d1\u05e7\u05e9\u05d5\u05ea",
                "\u05de\u05e1\u05e4\u05e8 \u05e6\u05e8\u05db\u05e0\u05d9\u05dd",
                "\u05e1\u05d4\"\u05db \u05e6\u05e8\u05db\u05e0\u05d9\u05dd",
                "total consumers",
                "total requests",
                "total",
            ],
            required=False,
        )
        if total_col is None:
            numeric_candidates = [c for c in df.select_dtypes(include=["number"]).columns if c != year_month_col]
            if numeric_candidates:
                total_col = numeric_candidates[0]
            else:
                for col in df.columns:
                    if col == year_month_col:
                        continue
                    coerced = pd.to_numeric(df[col], errors="coerce")
                    if coerced.notna().sum() > 0:
                        total_col = col
                        df[col] = coerced
                        break
        if total_col is None:
            raise KeyError("Missing expected total consumers column.")

        sector_col = resolve_column(
            [
                "\u05d1\u05d9\u05ea\u05d9/ \u05dc\u05d0 \u05d1\u05d9\u05ea\u05d9",
                "\u05d1\u05d9\u05ea\u05d9/\u05dc\u05d0 \u05d1\u05d9\u05ea\u05d9",
                "\u05d1\u05d9\u05ea\u05d9 / \u05dc\u05d0 \u05d1\u05d9\u05ea\u05d9",
                "\u05de\u05d2\u05d6\u05e8",
                "sector",
            ],
            required=False,
        )
        meter_col = resolve_column(
            [
                "\u05e1\u05d5\u05d2 \u05d0\u05e1\u05d3\u05e8\u05d4",
                "\u05e1\u05d5\u05d2 \u05d4\u05de\u05d5\u05e0\u05d4",
                "\u05e1\u05d5\u05d2 \u05de\u05d5\u05e0\u05d4",
                "meter type",
            ],
            required=False,
        )
        location_col = resolve_column(
            [
                "\u05de\u05d7\u05d5\u05d6",
                "\u05e9\u05dd \u05de\u05d7\u05d5\u05d6",
                "\u05e9\u05dd \u05d9\u05d9\u05e9\u05d5\u05d1",
                "\u05d9\u05d9\u05e9\u05d5\u05d1",
                "\u05d0\u05d6\u05d5\u05e8",
                "region",
                "district",
                "location",
            ],
            required=False,
        )

        rename_map = {
            year_month_col: "year_month",
            total_col: "total_consumers",
        }
        if sector_col:
            rename_map[sector_col] = "sector"
        if meter_col:
            rename_map[meter_col] = "meter_type"
        if location_col:
            rename_map[location_col] = "location"

        df = df.rename(columns=rename_map)

        # Parse dates (YYYY/MM or YYYY-MM) into month start.
        df["year_month"] = pd.to_datetime(df["year_month"], format="%Y/%m", errors="coerce").fillna(
            pd.to_datetime(df["year_month"], format="%Y-%m", errors="coerce")
        )
        df = df.dropna(subset=["year_month"])

        # Coerce counts to numeric.
        df["total_consumers"] = pd.to_numeric(df.get("total_consumers"), errors="coerce").fillna(0)

        df["month"] = df["year_month"].dt.to_period("M").dt.to_timestamp()
        df["month_label"] = df["month"].dt.strftime("%Y-%m")
        return df

    @staticmethod
    def _default_range(monthly_totals: pd.DataFrame) -> Tuple[str, str]:
        max_month = monthly_totals["month"].max()
        min_month = (max_month - pd.DateOffset(months=11)) if pd.notnull(max_month) else None
        if min_month is None:
            raise ValueError("Unable to determine default date range from data.")
        return to_iso_date(min_month), to_iso_date(max_month)

    @staticmethod
    def _compute_monthly(
        all_months: pd.DataFrame, start_date: Optional[str], end_date: Optional[str]
    ) -> Tuple[List[Dict], str, str, str, str]:
        grouped = (
            all_months.groupby(["month", "month_label"])["total_consumers"]
            .sum()
            .reset_index()
            .sort_values("month")
        )
        # Build cumulative totals first, then compute deltas using prior cumulative (avoids negatives).
        grouped["cumulative_total"] = grouped["total_consumers"].cumsum()
        grouped["new_additions"] = grouped["cumulative_total"].diff()

        min_month = grouped["month"].min()
        max_month = grouped["month"].max()

        requested_start = parse_date(start_date).replace(day=1) if start_date else None
        requested_end = parse_date(end_date).replace(day=1) if end_date else None

        if requested_start and requested_end:
            start_dt = requested_start
            end_dt = requested_end
        else:
            default_start, default_end = PrivateSuppliersService._default_range(grouped)
            start_dt = parse_date(default_start).replace(day=1)
            end_dt = parse_date(default_end).replace(day=1)

        earliest_month_label = to_iso_date(min_month)
        latest_month_label = to_iso_date(max_month)
        if start_dt < min_month:
            start_dt = min_month

        mask = (grouped["month"] >= start_dt) & (grouped["month"] <= end_dt)
        filtered = grouped.loc[mask].copy()

        records: List[Dict] = []
        for _, row in filtered.iterrows():
            records.append(
                {
                    "month": row["month_label"],
                    "total_consumers": float(row["cumulative_total"]),
                    "new_additions": None if pd.isna(row["new_additions"]) else float(row["new_additions"]),
                }
            )
        return (
            records,
            to_iso_date(requested_start) if requested_start else to_iso_date(start_dt),
            to_iso_date(requested_end) if requested_end else to_iso_date(end_dt),
            earliest_month_label,
            latest_month_label,
        )

    @staticmethod
    def _compute_segments(all_months: pd.DataFrame, start_dt, end_dt) -> Dict[str, List[Dict]]:
        segments: Dict[str, List[Dict]] = {}
        segment_mapping = {
            "location": "location",
            "sector": "sector",
            "meter_type": "meter_type",
        }
        for col, key in segment_mapping.items():
            if col not in all_months.columns:
                continue
            grouped = (
                all_months.groupby(["month", "month_label", col])["total_consumers"]
                .sum()
                .reset_index()
                .sort_values(["month", col])
            )
            segment_records: List[Dict] = []
            for segment_value, segment_df in grouped.groupby(col):
                # Respect requested date filter for segment series
                segment_df = segment_df[(segment_df["month"] >= start_dt) & (segment_df["month"] <= end_dt)]
                if segment_df.empty:
                    continue
                segment_df = segment_df.sort_values("month")
                segment_df["cumulative_total"] = segment_df["total_consumers"].cumsum()
                segment_df["new_additions"] = segment_df["cumulative_total"].diff().fillna(segment_df["total_consumers"])
                for _, row in segment_df.iterrows():
                    segment_records.append(
                        {
                            "month": row["month_label"],
                            key: PrivateSuppliersService._translate_segment_value(key, segment_value),
                            "total_consumers": float(row["cumulative_total"]),
                            "new_additions": float(row["new_additions"]),
                        }
                    )
            segments[key] = segment_records
        return segments

    @staticmethod
    def _translate_value(value: str) -> str:
        """
        Map common Hebrew values to English tokens for response consistency.
        Unknown values are returned as-is.
        """
        mapping = {
            "אסדרה קיימת": "existing_regulation",
            "תחרות באספקה": "competitive_supply",
            "ביתי": "residential",
            "לא ביתי": "non_residential",
            "מספקים וירטואליים": "virtual_suppliers",
            "מספקים עם אמצעי ייצור": "suppliers_with_generation",
        }
        return mapping.get(value, value)

    @staticmethod
    def _translate_meter(value: str) -> str:
        text = str(value or "").strip()
        lower = text.lower()
        if "smart" in lower:
            return "smart"
        if "basic" in lower:
            return "basic"
        return PrivateSuppliersService._translate_value(text)

    @staticmethod
    def _translate_segment_value(key: str, value: str) -> str:
        if key == "location":
            return str(value or "")
        if key == "meter_type":
            return PrivateSuppliersService._translate_meter(value)
        return PrivateSuppliersService._translate_value(value)


    @staticmethod
    def get_data(start_date: Optional[str], end_date: Optional[str], csv_path: Optional[Path] = None) -> Dict:
        df = PrivateSuppliersService._load_dataframe(csv_path)
        monthly, start_iso, end_iso, earliest_month, latest_month = PrivateSuppliersService._compute_monthly(
            df, start_date, end_date
        )
        # Filter window for segments uses month boundaries of the actual filtered data.
        start_dt = parse_date(start_iso).replace(day=1)
        end_dt = parse_date(end_iso).replace(day=1)
        segments = PrivateSuppliersService._compute_segments(df, start_dt, end_dt)

        notes: List[str] = []
        requested_start_iso = None
        if start_date:
            try:
                requested_start = parse_date(start_date)
                requested_start_iso = to_iso_date(requested_start.replace(day=1))
                if requested_start < parse_date(earliest_month):
                    notes.append(f"Data available from {earliest_month}; data begins from earliest available month.")
            except Exception:
                requested_start_iso = start_date

        if end_date:
            try:
                requested_end = parse_date(end_date).replace(day=1)
                if requested_end < parse_date(latest_month):
                    notes.append("Data clipped to requested end_date.")
            except Exception:
                pass

        note = "; ".join(notes) if notes else None

        return {
            "start_date": requested_start_iso or start_iso,
            "end_date": end_iso,
            "unit": "count",
            "labels": {
                "month": "Month",
                "total_consumers": "Total Consumers",
                "new_additions": "New Additions",
            },
            "data": monthly,
            "segments": segments,
            "note": note,
        }

    @staticmethod
    def to_excel(payload: Dict) -> bytes:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(payload.get("data", [])).to_excel(writer, sheet_name="Summary", index=False)
            for key, rows in payload.get("segments", {}).items():
                if not rows:
                    continue
                pd.DataFrame(rows).to_excel(writer, sheet_name=key, index=False)
        buffer.seek(0)
        return buffer.getvalue()
