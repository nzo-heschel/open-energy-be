# app/services/switching_requests_service.py
from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from app.utils.enums import DataFileSource
from app.services.data_file_manager import ensure_fresh_data_file

LOCAL_CACHE = Path(os.getenv("SWITCHING_REQUESTS_CACHE", "switching_requests.csv"))

STATUS_COLUMN_PATTERNS = [
    "status",
    "request status",
    "\u05e1\u05d8\u05d8\u05d5\u05e1",
    "\u05e1\u05d8\u05d8\u05d5\u05e1 \u05d1\u05e7\u05e9\u05d4",
    "\u05e1\u05d8\u05d8\u05d5\u05e1 \u05d1\u05e7\u05e9\u05d5\u05ea",
]
REJECTION_COLUMN_PATTERNS = [
    "rejection reason",
    "reject reason",
    "rejection",
    "reject",
    "decline",
    "denied",
    "\u05e1\u05d9\u05d1\u05ea \u05d3\u05d7\u05d9\u05d4",
    "\u05e1\u05d9\u05d1\u05ea \u05d3\u05d7\u05d9\u05d9\u05d4",
    "\u05e1\u05d9\u05d1\u05d4 \u05dc\u05d3\u05d7\u05d9\u05d4",
    "\u05e1\u05d9\u05d1\u05d4 \u05dc\u05d3\u05d7\u05d9\u05d9\u05d4",
    "\u05e1\u05d9\u05d1\u05ea \u05e1\u05d8\u05d8\u05d5\u05e1",
    "\u05e1\u05d9\u05d1\u05d5\u05ea \u05dc\u05e1\u05d8\u05d8\u05d5\u05e1",
    "\u05e4\u05d9\u05e8\u05d5\u05d8 \u05e1\u05d9\u05d1\u05ea \u05e1\u05d8\u05d8\u05d5\u05e1",
]
STATUS_EXCLUDE_PATTERNS = [
    "reason",
    "reject",
    "rejection",
    "\u05e1\u05d9\u05d1\u05d4",
    "\u05d3\u05d7\u05d9\u05d4",
]


def _load_dataframe(csv_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Load the switching-requests CSV (or Excel), normalizing headers.
    """
    csv_path = csv_path or ensure_fresh_data_file(DataFileSource.SWITCHING_REQUESTS)
    df = None
    if csv_path.suffix.lower() in (".xls", ".xlsx"):
        try:
            df = pd.read_excel(csv_path)
        except Exception:
            df = None
    if df is None:
        for enc in ("cp1255", "utf-8-sig", "latin1"):
            try:
                df = pd.read_csv(csv_path, encoding=enc)
                break
            except Exception:
                df = None
    if df is None:
        raise ValueError("Unable to parse switching-requests CSV.")

    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
    return df


def _normalize_col_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\ufeff", "").replace("\u00a0", " ")
    return re.sub(r"[\s/._-]+", "", text)


def _find_column(
    columns: List[str],
    patterns: List[str],
    exclude_patterns: Optional[List[str]] = None,
) -> Optional[str]:
    normalized = [(_normalize_col_name(col), col) for col in columns]
    excludes = [_normalize_col_name(pat) for pat in (exclude_patterns or []) if pat]

    def is_excluded(normalized_name: str) -> bool:
        return any(ex and ex in normalized_name for ex in excludes)

    for pattern in patterns:
        pattern_norm = _normalize_col_name(pattern)
        for normalized_name, col in normalized:
            if normalized_name == pattern_norm and not is_excluded(normalized_name):
                return col

    for pattern in patterns:
        pattern_norm = _normalize_col_name(pattern)
        if not pattern_norm:
            continue
        for normalized_name, col in normalized:
            if pattern_norm in normalized_name and not is_excluded(normalized_name):
                return col
    return None


def _normalize_customer_type(value: str) -> str:
    text = str(value or "").lower()
    if "ביתי" in text and "לא" not in text:
        return "residential"
    if "non" in text:
        return "non_residential"
    if "לא" in text:
        return "non_residential"
    return "residential"


def _attach_customer_type(df: pd.DataFrame) -> pd.DataFrame:
    customer_col = next((c for c in df.columns if "ביתי" in c), None)
    if not customer_col:
        df["customer_type"] = "unknown"
    else:
        df["customer_type"] = df[customer_col].apply(_normalize_customer_type)
    return df


def _filter_customer_type(df: pd.DataFrame, customer_type: Optional[str]) -> pd.DataFrame:
    if not customer_type:
        return df
    norm = customer_type.lower()
    allowed = {"residential", "non_residential"}
    if norm not in allowed:
        raise ValueError(f"customer_type must be one of {sorted(allowed)}")
    return df[df["customer_type"] == norm]


def _group_counts(df: pd.DataFrame, key: str, translate: bool = False) -> List[Dict]:
    if key not in df.columns:
        return []
    grouped = df.groupby(key).size().reset_index(name="count").sort_values("count", ascending=False)
    results = []
    for _, row in grouped.iterrows():
        label = str(row[key])
        if translate:
            label = _translate_value(label)
        results.append({"label": label, "count": int(row["count"])})
    return results


def _bucket_connection_size(df: pd.DataFrame) -> List[Dict]:
    size_col = next((c for c in df.columns if "gva" in c.lower()), None)
    if not size_col or df[size_col].dropna().empty:
        return []
    bins = [0, 0.05, 0.1, 0.5, 1, 5, float("inf")]
    labels = ["0-0.05", "0.05-0.1", "0.1-0.5", "0.5-1", "1-5", "5+"]
    bucketed = pd.cut(df[size_col], bins=bins, labels=labels, include_lowest=True)
    grouped = bucketed.value_counts().sort_index()
    return [{"label": str(idx), "count": int(val)} for idx, val in grouped.items()]


def _translate_value(value: str) -> str:
    translations = {
        "המרכז": "central",
        "תל אביב": "tel_aviv",
        "הדרום": "south",
        "חיפה": "haifa",
        "ירושלים": "jerusalem",
        "הצפון": "north",
        "אזור יהודה ושומרון": "judea_samaria",
        "אחר": "other",
        "נמוך": "low",
        "גבוה": "high",
        "בינוני": "medium",
        "חכם": "smart",
        "בסיסי": "basic",
        "אסדרה קיימת": "existing_regulation",
        "תחרות באספקה": "competitive_supply",
        "עליון": "extra_high",
    }
    text = str(value or "").strip()
    if text in translations:
        return translations[text]
    # If still Hebrew / non-ASCII, collapse to "other".
    if any(ord(ch) > 127 for ch in text):
        return "other"
    return text or "unknown"


def build_payload(customer_type: Optional[str] = None, csv_path: Optional[Path] = None) -> Dict:
    df = _load_dataframe(csv_path)
    df = _attach_customer_type(df)
    df = _filter_customer_type(df, customer_type)

    # Column detection for status/rejection if present.
    status_col = _find_column(
        df.columns,
        STATUS_COLUMN_PATTERNS,
        exclude_patterns=STATUS_EXCLUDE_PATTERNS,
    )
    rejection_col = _find_column(df.columns, REJECTION_COLUMN_PATTERNS)
    region_col = next((c for c in df.columns if "????" in c), None)
    voltage_col = next((c for c in df.columns if "???" in c), None)
    meter_col = next((c for c in df.columns if "????" in c), None)
    regulation_col = next((c for c in df.columns if "?????" in c), None)

    charts = {
        "by_customer_type": {
            "label": "Requests by customer type",
            "data": _group_counts(df, "customer_type"),
        },
        "by_region": {
            "label": "Requests by region",
            "data": _group_counts(df, region_col, translate=True) if region_col else [],
        },
        "by_voltage": {
            "label": "Requests by voltage level",
            "data": _group_counts(df, voltage_col, translate=True) if voltage_col else [],
        },
        "by_meter_type": {
            "label": "Requests by meter type",
            "data": _group_counts(df, meter_col, translate=True) if meter_col else [],
        },
        "by_regulation": {
            "label": "Requests by regulation",
            "data": _group_counts(df, regulation_col, translate=True) if regulation_col else [],
        },
        "by_connection_size": {
            "label": "Requests by connection size (GVA)",
            "data": _bucket_connection_size(df),
        },
        "requests_by_status": {
            "label": "Requests by status",
            "data": _group_counts(df, status_col) if status_col else [],
        },
        "requests_by_rejection_reason": {
            "label": "Requests by rejection reason",
            "data": _group_counts(df, rejection_col) if rejection_col else [],
        },
        "total_requests": {
            "label": "Total requests",
            "data": [{"count": int(len(df))}],
        },
    }

    return {
        "filter": customer_type or "all",
        "unit": "count",
        "charts": charts,
    }


def to_excel(payload: Dict) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_rows = [{"metric": "filter", "value": payload.get("filter")}]
        summary_rows.append(
            {
                "metric": "total_requests",
                "value": payload.get("charts", {})
                .get("total_requests", {})
                .get("data", [{}])[0]
                .get("count"),
            }
        )
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        for key, chart in payload.get("charts", {}).items():
            data = chart.get("data") or []
            if not data:
                continue
            pd.DataFrame(data).to_excel(writer, sheet_name=key, index=False)
    buffer.seek(0)
    return buffer.getvalue()
