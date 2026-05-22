from __future__ import annotations

import os
import re
from datetime import datetime
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.utils.date_utils import parse_date, to_iso_date
from app.utils.enums import DataFileSource
from app.services.data_file_manager import ensure_fresh_data_file, data_file_status
from app.services.csv_downloader_service import ensure_fresh_or_download

DEFAULT_CSV_PATH = Path(os.getenv("PRIVATE_SUPPLIERS_CSV_PATH", "Files_Netunei_hashmal_mp_tzarchan.csv"))
HEADER_MARKERS = {
    "year / month",
    "type of regulation",
    "supply competition / existing regulation",
    "domestic / non-domestic",
    "reasons for the status",
    "status reason details",
    "status",
    "number of requests",
    "locality name",
    "district",
    "district name",
    "regulation",
    "meter type",
    "(gva) connection size",
    "אסדרה",
    "מתח",
    "סוג המונה",
    "ביתי/ לא ביתי",
    "שנה/ חודש",
    "סוג אסדרה",
    "תחרות באספקה/ אסדרה קיימת",
    "סיבות לסטטוס",
    "פירוט סיבת סטטוס",
    "סטטוס",
    "מספר בקשות",
    "רגולציה",
}


@dataclass
class PrivateSupplierRecord:
    month: str
    total_consumers: float
    new_additions: float


class PrivateSuppliersService:
    @staticmethod
    def _derive_month_from_path(csv_path: Path) -> pd.Timestamp:
        """
        If the file name contains a dd-mm-YYYY suffix, use it; otherwise fall back to mtime.
        """
        match = re.search(r"_(\d{2}-\d{2}-\d{4})", csv_path.name)
        if match:
            dt = datetime.strptime(match.group(1), "%d-%m-%Y")
        else:
            dt = datetime.fromtimestamp(csv_path.stat().st_mtime)
        return pd.Timestamp(dt.strftime("%Y-%m-01"))

    @staticmethod
    def _normalize_col(value: str) -> str:
        text = str(value or "").strip().lower()
        text = text.replace("\ufeff", "").replace("\u00a0", " ")
        return re.sub(r"[\s/._-]+", "", text)

    @staticmethod
    def _looks_like_header_row(row: pd.Series) -> bool:
        values = [str(v).strip().lower() for v in row.tolist()]
        hits = sum(1 for v in values if v in HEADER_MARKERS)
        return hits >= max(3, len(values) // 2)

    @staticmethod
    def _resolve_column(df: pd.DataFrame, possible: list[str], required: bool = True) -> Optional[str]:
        normalized_cols = {PrivateSuppliersService._normalize_col(col): col for col in df.columns}
        for name in possible:
            if name in df.columns:
                return name
        for name in possible:
            normalized = PrivateSuppliersService._normalize_col(name)
            if normalized in normalized_cols:
                return normalized_cols[normalized]
        for col in df.columns:
            col_norm = PrivateSuppliersService._normalize_col(col)
            for name in possible:
                name_norm = PrivateSuppliersService._normalize_col(name)
                if name_norm and name_norm in col_norm:
                    return col
        if required:
            raise KeyError(f"Missing expected column(s): {possible}")
        return None

    @staticmethod
    def _load_dataframe(csv_path: Optional[Path] = None) -> Tuple[pd.DataFrame, bool]:
        csv_path = csv_path or ensure_fresh_or_download(DataFileSource.PRIVATE_SUPPLIERS)

        df: Optional[pd.DataFrame] = None
        last_err: Optional[Exception] = None
        if csv_path.suffix.lower() in (".xls", ".xlsx"):
            try:
                df = pd.read_excel(csv_path)
            except Exception as exc:
                last_err = exc
        else:
            for enc in ("cp1255", "utf-8-sig", "latin1"):
                try:
                    df = pd.read_csv(csv_path, encoding=enc)
                    break
                except Exception as exc:
                    last_err = exc
        if df is None:
            raise last_err or ValueError("Unable to load CSV")

        df.columns = [col.replace("\ufeff", "").strip() for col in df.columns]

        if not df.empty and PrivateSuppliersService._looks_like_header_row(df.iloc[0]):
            df = df.iloc[1:]

        year_month_candidates = [
            "year / month",
            "year/month",
            "year-month",
            "year_month",
            "year month",
            "month",
            "date",
            "שנה/ חודש",
            "שנה/חודש",
        ]
        total_candidates = [
            "total consumers",
            "total requests",
            "total",
            "number of requests",
            "count",
            "מספר בקשות",
            'סה"כ בקשות',
            'סה"כ צרכנים',
        ]
        sector_candidates = [
            "sector",
            "residential / non-residential",
            "residential/non-residential",
            "domestic / non-domestic",
            "domestic/non-domestic",
            "residential",
            "ביתי/ לא ביתי",
        ]
        meter_candidates = [
            "meter type",
            "type of meter",
            "smart/basic",
            "סוג המונה",
        ]
        regulation_candidates = [
            "regulation",
            "type of regulation",
            "supply competition / existing regulation",
            "סוג אסדרה",
            "תחרות באספקה/ אסדרה קיימת",
            "אסדרה",
        ]
        status_candidates = [
            "status",
            "request status",
            "approval status",
            "סטטוס",
        ]
        rejection_candidates = [
            "status reason details",
            "reasons for the status",
            "rejection reason",
            "reason",
            "סיבות לסטטוס",
            "פירוט סיבת סטטוס",
        ]
        district_candidates = [
            "district",
            "district name",
            "שם מחוז",
            "מחוז",
        ]


        year_month_col = PrivateSuppliersService._resolve_column(df, year_month_candidates, required=False)
        total_col = PrivateSuppliersService._resolve_column(df, total_candidates, required=False)
        sector_col = PrivateSuppliersService._resolve_column(df, sector_candidates, required=False)
        meter_col = PrivateSuppliersService._resolve_column(df, meter_candidates, required=False)
        regulation_col = PrivateSuppliersService._resolve_column(df, regulation_candidates, required=False)
        status_col = PrivateSuppliersService._resolve_column(df, status_candidates, required=False)
        rejection_col = PrivateSuppliersService._resolve_column(df, rejection_candidates, required=False)
        district_col = PrivateSuppliersService._resolve_column(df, district_candidates, required=False)


        rename_map: Dict[str, str] = {}
        if year_month_col:
            rename_map[year_month_col] = "year_month"
        if total_col:
            rename_map[total_col] = "total_consumers"
        if sector_col:
            rename_map[sector_col] = "sector"
        if meter_col:
            rename_map[meter_col] = "meter_type"
        if regulation_col:
            rename_map[regulation_col] = "regulation_type"
        if status_col:
            rename_map[status_col] = "status"
        if rejection_col:
            rename_map[rejection_col] = "rejection_reason"
        if district_col:
            rename_map[district_col] = "district"

        df = df.rename(columns=rename_map)

        # Drop section-banner / aggregate-summary rows the Authority's CSV
        # interleaves into the data. They have valid district/sector but
        # blank (NaN or empty string) ``regulation_type`` and
        # ``meter_type`` — the gov's own dashboard excludes them, and the
        # client flagged them as "the headline row" being counted. In the
        # May-2026 file this drops 14 rows and brings our per-district
        # totals to match the gov chart exactly (e.g. המרכז 133,727 →
        # 133,722). The check tolerates both NaN and whitespace-only
        # cells, and only runs for columns the file actually provides so
        # older CSV shapes still load.
        required_categorical = [
            col for col in ("regulation_type", "meter_type")
            if col in df.columns
        ]
        if required_categorical:
            keep = pd.Series(True, index=df.index)
            for col in required_categorical:
                series = df[col]
                non_blank = series.astype(str).str.strip().str.lower()
                keep &= series.notna() & (non_blank != "") & (non_blank != "nan")
            df = df[keep].copy()

        derived_month = False
        if "year_month" in df.columns:
            df["year_month"] = pd.to_datetime(
                df["year_month"],
                format="%Y/%m",
                errors="coerce",
            ).fillna(pd.to_datetime(df["year_month"], errors="coerce"))
            df = df.dropna(subset=["year_month"])
        else:
            derived_month = True
            month_ts = PrivateSuppliersService._derive_month_from_path(csv_path)
            df["year_month"] = month_ts

        if "total_consumers" in df.columns:
            df["total_consumers"] = pd.to_numeric(df["total_consumers"], errors="coerce").fillna(0)
        else:
            # This dataset is per-connection; count rows as consumers.
            df["total_consumers"] = 1

        df["month"] = df["year_month"].dt.to_period("M").dt.to_timestamp()
        df["month_label"] = df["month"].dt.strftime("%Y-%m")

        if "sector" in df.columns:
            df["sector"] = df["sector"].apply(PrivateSuppliersService._translate_value)
        if "meter_type" in df.columns:
            df["meter_type"] = df["meter_type"].apply(PrivateSuppliersService._translate_meter)
        if "regulation_type" in df.columns:
            df["regulation_type"] = df["regulation_type"].apply(PrivateSuppliersService._translate_value)
        if "status" in df.columns:
            df["status"] = df["status"].apply(PrivateSuppliersService._translate_value)
        if "rejection_reason" in df.columns:
            df["rejection_reason"] = df["rejection_reason"].apply(PrivateSuppliersService._translate_value)

        if df.empty:
            raise ValueError("No data rows found in private suppliers source.")

        return df, derived_month

    @staticmethod
    def _default_range(monthly_totals: pd.DataFrame) -> Tuple[str, str]:
        max_month = monthly_totals["month"].max()
        min_month = monthly_totals["month"].min()
        if pd.isna(max_month) or pd.isna(min_month):
            raise ValueError("Unable to determine default date range from data.")
        min_month = max_month - pd.DateOffset(months=11)
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
        grouped["new_additions"] = grouped["total_consumers"].diff().fillna(grouped["total_consumers"])

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
        if end_dt > max_month:
            end_dt = max_month
        if end_dt < start_dt:
            end_dt = start_dt

        mask = (grouped["month"] >= start_dt) & (grouped["month"] <= end_dt)
        filtered = grouped.loc[mask].copy()

        records: List[Dict] = []
        for _, row in filtered.iterrows():
            records.append(
                {
                    "month": row["month_label"],
                    "total_consumers": float(row["total_consumers"]),
                    "new_additions": None if pd.isna(row["new_additions"]) else float(row["new_additions"]),
                }
            )
        return (
            records,
            to_iso_date(start_dt),
            to_iso_date(end_dt),
            earliest_month_label,
            latest_month_label,
        )

    @staticmethod
    def _compute_segments(all_months: pd.DataFrame, start_dt, end_dt) -> Dict[str, List[Dict]]:
        segments: Dict[str, List[Dict]] = {}
        segment_mapping = {
            "regulation_type": "regulation_type",
            "sector": "sector",
            "meter_type": "meter_type",
            "district": "district",

            "status": "status",
            "rejection_reason": "rejection_reason",
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
                segment_df = segment_df[(segment_df["month"] >= start_dt) & (segment_df["month"] <= end_dt)]
                if segment_df.empty:
                    continue
                segment_df = segment_df.sort_values("month")
                segment_df["new_additions"] = segment_df["total_consumers"].diff().fillna(segment_df["total_consumers"])
                for _, row in segment_df.iterrows():
                    segment_records.append(
                        {
                            "month": row["month_label"],
                            key: PrivateSuppliersService._translate_segment_value(key, segment_value),
                            "total_consumers": float(row["total_consumers"]),
                            "new_additions": float(row["new_additions"]),
                        }
                    )
            if segment_records:
                segments[key] = segment_records
        # Backward compatibility: if legacy "location" was present, expose as regulation_type.
        if "location" in segments and "regulation_type" not in segments:
            segments["regulation_type"] = segments.pop("location")
        for expected in ("regulation_type", "sector", "meter_type", "district"):
            segments.setdefault(expected, [])
        return segments

    @staticmethod
    def _translate_value(value: str) -> str:
        mapping = {
            "ביתי": "residential",
            "לא ביתי": "non_residential",
            "אסדרה קיימת": "existing_regulation",
            "תחרות באספקה": "competitive_supply",
            "חכם": "smart",
            "בסיסי": "basic",
            "נמוך": "low",
            "גבוה": "high",
            "עליון": "extra_high",
            "approved": "approved",
            "rejected": "rejected",
            "reject": "rejected",
        }
        text = str(value or "").strip()
        if text in mapping:
            return mapping[text]
        lowered = text.lower().strip()
        lowered = lowered.replace(" ", "_").replace("-", "_").replace("/", "_")
        if lowered in mapping:
            return mapping[lowered]
        return lowered or "unknown"

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
        if key == "meter_type":
            return PrivateSuppliersService._translate_meter(value)
        return PrivateSuppliersService._translate_value(value)

    @staticmethod
    def get_data(start_date: Optional[str], end_date: Optional[str], csv_path: Optional[Path] = None) -> Dict:
        df, derived_month = PrivateSuppliersService._load_dataframe(csv_path)
        status = data_file_status(DataFileSource.PRIVATE_SUPPLIERS)
        monthly, start_iso, end_iso, earliest_month, latest_month = PrivateSuppliersService._compute_monthly(
            df, start_date, end_date
        )
        start_dt = parse_date(start_iso).replace(day=1)
        end_dt = parse_date(end_iso).replace(day=1)
        segments = PrivateSuppliersService._compute_segments(df, start_dt, end_dt)

        notes: List[str] = []
        if start_date:
            try:
                requested_start = parse_date(start_date)
                if requested_start < parse_date(earliest_month):
                    notes.append(f"Data available from {earliest_month}; data begins from earliest available month.")
            except Exception:
                pass

        if end_date:
            try:
                requested_end = parse_date(end_date).replace(day=1)
                if requested_end < parse_date(earliest_month):
                    notes.append(f"Requested end_date before available data; data begins from {earliest_month}.")
                elif requested_end < parse_date(latest_month):
                    notes.append("Data clipped to requested end_date.")
                elif requested_end > parse_date(latest_month):
                    notes.append(f"Data clipped to latest available month {latest_month}.")
            except Exception:
                pass

        if derived_month:
            notes.append("Month derived from file name/modified date because no date column was provided.")

        if status.get("status") == "stale":
            age_days = status.get("age_days")
            age_text = str(int(age_days)) if isinstance(age_days, (int, float)) else "an unknown number of"
            notes.append(
                f"Data file is old ({age_text} days). Upload a fresh file for the latest readings."
            )

        note = "; ".join(notes) if notes else None

        return {
            "start_date": start_iso,
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
                pd.DataFrame(rows).to_excel(writer, sheet_name=key, index=False)
        buffer.seek(0)
        return buffer.getvalue()
