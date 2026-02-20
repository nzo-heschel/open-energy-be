# app/services/switching_requests_service.py
from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from app.utils.enums import DataFileSource
from app.services.data_file_manager import ensure_fresh_data_file, data_file_status

DEFAULT_CSV_PATH = Path(os.getenv("SWITCHING_REQUESTS_CSV_PATH", "Files_Netunei_hashmal_mp_niyud.xlsx"))
HEADER_MARKERS = {
    "year / month",
    "type of regulation",
    "supply competition / existing regulation",
    "domestic / non-domestic",
    "reasons for the status",
    "status reason details",
    "status",
    "number of requests",
    "ביתי/ לא ביתי",
    "סיבות לסטטוס",
    "פירוט סיבת סטטוס",
    "סטטוס",
    "מספר בקשות",
    "סוג אסדרה",
}

REJECTION_REASON_ORDER = [
    "missing_power_of_attorney",
    "meter_issues",
    "request_form_issues",
    "other",
]


def _normalize_reason(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("_", " ").replace("-", " ").replace("/", " ").strip().lower()


REJECTION_REASON_MAP = {
    _normalize_reason("missing_power_of_attorney"): "missing_power_of_attorney",
    _normalize_reason("missing power of attorney"): "missing_power_of_attorney",
    _normalize_reason("ייפוי כוח חסר/לא תקין"): "missing_power_of_attorney",
    _normalize_reason("meter_issues"): "meter_issues",
    _normalize_reason("meter issues"): "meter_issues",
    _normalize_reason("בעיות תקשורת במונה"): "meter_issues",
    _normalize_reason("request_form_issues"): "request_form_issues",
    _normalize_reason("problems in filling out the request"): "request_form_issues",
    _normalize_reason("בעיות במילוי בקשת הניוד"): "request_form_issues",
    _normalize_reason("other"): "other",
    _normalize_reason("אחר"): "other",
}


def _normalize_col(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\ufeff", "").replace("\u00a0", " ")
    return re.sub(r"[\s/._-]+", "", text)


def _looks_like_header_row(row: pd.Series) -> bool:
    values = [str(v).strip().lower() for v in row.tolist()]
    hits = sum(1 for v in values if v in HEADER_MARKERS)
    return hits >= max(3, len(values) // 2)


def _resolve_column(df: pd.DataFrame, possible: list[str], required: bool = True) -> Optional[str]:
    normalized_cols = {_normalize_col(col): col for col in df.columns}
    for name in possible:
        if name in df.columns:
            return name
    for name in possible:
        normalized = _normalize_col(name)
        if normalized in normalized_cols:
            return normalized_cols[normalized]
    for col in df.columns:
        col_norm = _normalize_col(col)
        for name in possible:
            name_norm = _normalize_col(name)
            if name_norm and name_norm in col_norm:
                return col
    if required:
        raise KeyError(f"Missing expected columns matching: {possible}")
    return None


def _translate_value(value: str) -> str:
    mapping = {
        "ביתי": "residential",
        "לא ביתי": "non_residential",
        "אסדרה קיימת": "existing_regulation",
        "תחרות באספקה": "competitive_supply",
        "מספקים עם אמצעי ייצור": "suppliers_with_generation",
        "מספקים וירטואליים": "virtual_suppliers",
        "הושלם": "approved",
        "נדחה": "rejected",
        "???? ?????": "approved",
        "???": "other",
        "????? ??? ???/?? ????": "missing_power_of_attorney",
        "????? ?????? ?????": "meter_issues",
        "????? ?????? ???? ?????": "request_form_issues",

    }
    text = str(value or "").strip()
    if text in mapping:
        return mapping[text]
    lowered = text.lower().strip()
    lowered = lowered.replace(" ", "_").replace("-", "_").replace("/", "_")
    if "reject" in lowered:
        return "rejected"
    if "approve" in lowered:
        return "approved"
    if lowered in mapping:
        return mapping[lowered]
    return lowered or "unknown"


def _map_rejection_reason(value: str) -> str:
    normalized = _normalize_reason(value)
    mapped = REJECTION_REASON_MAP.get(normalized)
    if mapped:
        return mapped
    if "power of attorney" in normalized or "?????" in normalized:
        return "missing_power_of_attorney"
    if "meter" in normalized or "????" in normalized:
        return "meter_issues"
    if "request" in normalized or "????" in normalized:
        return "request_form_issues"
    return "other"


def _load_dataframe(csv_path: Optional[Path] = None) -> pd.DataFrame:
    csv_path = csv_path or ensure_fresh_data_file(DataFileSource.SWITCHING_REQUESTS, allow_stale=True)
    df = None
    if csv_path.suffix.lower() in (".xls", ".xlsx"):
        try:
            df = pd.read_excel(csv_path)
        except Exception:
            df = None
    if df is None:
        for enc in ("utf-8-sig", "cp1255", "latin1"):
            try:
                df = pd.read_csv(csv_path, encoding=enc)
                break
            except Exception:
                df = None
    if df is None:
        raise ValueError("Unable to parse switching-requests data file.")

    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
    if not df.empty and _looks_like_header_row(df.iloc[0]):
        df = df.iloc[1:]
    return df


def _group_sum(df: pd.DataFrame, key: str, value_col: str) -> List[Dict]:
    if key not in df.columns:
        return []
    grouped = (
        df.groupby(key)[value_col]
        .sum()
        .reset_index()
        .sort_values(value_col, ascending=False)
    )
    results = []
    for _, row in grouped.iterrows():
        results.append({"label": _translate_value(row[key]), "count": int(row[value_col])})
    return results


def _summarize_rejection_reasons(df: pd.DataFrame, value_col: str) -> List[Dict]:
    if df.empty or "rejection_reason" not in df.columns:
        return [{"label": reason, "count": 0} for reason in REJECTION_REASON_ORDER]
    grouped = df.groupby("rejection_reason")[value_col].sum().to_dict()
    results = []
    for reason in REJECTION_REASON_ORDER:
        results.append({"label": reason, "count": int(grouped.get(reason, 0))})
    return results


def _monthly_rejection_breakdown(df: pd.DataFrame, value_col: str) -> List[Dict]:
    if df.empty or "rejection_reason" not in df.columns:
        return []
    grouped = (
        df.groupby(["month_label", "rejection_reason"])[value_col]
        .sum()
        .reset_index()
    )
    pivot = grouped.pivot(index="month_label", columns="rejection_reason", values=value_col).fillna(0)
    for reason in REJECTION_REASON_ORDER:
        if reason not in pivot.columns:
            pivot[reason] = 0
    pivot = pivot[REJECTION_REASON_ORDER].sort_index()

    results: List[Dict] = []
    for month, row in pivot.iterrows():
        item = {"month": month}
        total = 0
        for reason in REJECTION_REASON_ORDER:
            count = int(row.get(reason, 0))
            item[reason] = count
            total += count
        item["total_rejections"] = total
        results.append(item)
    return results


def build_payload(
    customer_type: Optional[str] = None,
    year: Optional[int] = None,
    csv_path: Optional[Path] = None,
) -> Dict:
    df = _load_dataframe(csv_path)
    status = data_file_status(DataFileSource.SWITCHING_REQUESTS)

    year_month_col = _resolve_column(
        df,
        ["year / month", "year/month", "year-month", "year_month", "שנה/ חודש"],
        required=True,
    )
    requests_col = _resolve_column(
        df,
        ["number of requests", "מספר בקשות", "total requests", "count"],
        required=True,
    )
    regulation_col = _resolve_column(df, ["type of regulation", "סוג אסדרה"], required=False)
    competition_col = _resolve_column(
        df,
        ["supply competition / existing regulation", "תחרות באספקה/ אסדרה קיימת"],
        required=False,
    )
    customer_col = _resolve_column(
        df,
        [
            "domestic / non-domestic",
            "residential / non-residential",
            "residential/non-residential",
            "ביתי/ לא ביתי",
        ],
        required=False,
    )
    status_col = _resolve_column(df, ["status", "סטטוס"], required=False)

    status_reason_col = _resolve_column(
        df,
        [
            "reasons for the status",
            "\u05e1\u05d9\u05d1\u05d5\u05ea \u05dc\u05e1\u05e1\u05d8\u05d5\u05e1",
            "\u05e1\u05d9\u05d1\u05d5\u05ea \u05dc\u05e1\u05d8\u05d8\u05d5\u05e1",
            "\u05e1\u05d9\u05d1\u05d5\u05ea \u05dc\u05e1\u05d8\u05d8\u05d8\u05d5\u05e1",
        ],
        required=False,
    )

    status_reason_details_col = _resolve_column(
        df,
        ["status reason details", "פירוט סיבת סטטוס"],
        required=False,
    )

    rename_map = {
        year_month_col: "year_month",
        requests_col: "requests_count",
    }
    if regulation_col:
        rename_map[regulation_col] = "regulation_type"
    if competition_col:
        rename_map[competition_col] = "competition_type"
    if customer_col:
        rename_map[customer_col] = "customer_type"
    if status_col:
        rename_map[status_col] = "status"
    if status_reason_col:
        rename_map[status_reason_col] = "status_reason"
    if status_reason_details_col:
        rename_map[status_reason_details_col] = "status_reason_details"
    df = df.rename(columns=rename_map)

    df["year_month"] = pd.to_datetime(df["year_month"], errors="coerce")
    df = df.dropna(subset=["year_month"])
    df["requests_count"] = pd.to_numeric(df["requests_count"], errors="coerce").fillna(0)
    df["year"] = df["year_month"].dt.year
    df["month_label"] = df["year_month"].dt.to_period("M").dt.strftime("%Y-%m")

    if "customer_type" in df.columns:
        df["customer_type"] = df["customer_type"].apply(_translate_value)
    if "regulation_type" in df.columns:
        df["regulation_type"] = df["regulation_type"].apply(_translate_value)
    if "competition_type" in df.columns:
        df["competition_type"] = df["competition_type"].apply(_translate_value)
    if "status" in df.columns:
        df["status"] = df["status"].apply(_translate_value)
    if "status_reason" in df.columns:
        df["status_reason"] = df["status_reason"].apply(_translate_value)
    if "status_reason_details" in df.columns:
        df["status_reason_details"] = df["status_reason_details"].apply(_translate_value)

    available_years = sorted(df["year"].dropna().unique().tolist())
    if year:
        if year < 2021:
            raise ValueError("year must be 2021 or later")
        df = df[df["year"] == year]

    if customer_type:
        normalized_customer_type = _translate_value(customer_type)
        allowed = {"residential", "non_residential", "unknown"}
        if normalized_customer_type not in allowed:
            raise ValueError(f"customer_type must be one of {sorted(allowed)}")
        if "customer_type" in df.columns:
            df = df[df["customer_type"] == normalized_customer_type]
        elif normalized_customer_type != "unknown":
            df = df.iloc[0:0]

    total_requests = int(df["requests_count"].sum())

    rejected_df = df.copy()
    status_present = "status" in df.columns
    if status_present:
        rejected_df = df[df["status"] == "rejected"].copy()

    reason_cols = [c for c in ("status_reason", "status_reason_details") if c in df.columns]
    if rejected_df.empty and reason_cols:
        # Fallback: if status mapping fails, infer rejections by presence of a reason.
        rejected_df = df[df[reason_cols].notna().any(axis=1)].copy()

    if "status_reason" in rejected_df.columns:
        rejected_df["rejection_reason"] = rejected_df["status_reason"].apply(_map_rejection_reason)
    elif "status_reason_details" in rejected_df.columns:
        rejected_df["rejection_reason"] = rejected_df["status_reason_details"].apply(_map_rejection_reason)
    total_rejections = int(rejected_df["requests_count"].sum()) if not rejected_df.empty else 0

    monthly_totals = (
        df.groupby("month_label")["requests_count"]
        .sum()
        .reset_index()
        .sort_values("month_label")
        .rename(columns={"month_label": "month", "requests_count": "requests"})
        .to_dict(orient="records")
    )

    charts = {
        "requests_by_status": {
            "label": "Total requests by status",
            "data": _group_sum(df, "status", "requests_count") if "status" in df.columns else [],
        },
        "requests_by_customer_type": {
            "label": "Total requests by customer type",
            "data": _group_sum(df, "customer_type", "requests_count") if "customer_type" in df.columns else [],
        },
        "requests_by_regulation_type": {
            "label": "Total requests by regulation type",
            "data": _group_sum(df, "regulation_type", "requests_count") if "regulation_type" in df.columns else [],
        },
        "requests_by_competition_type": {
            "label": "Total requests by supply competition/existing regulation",
            "data": _group_sum(df, "competition_type", "requests_count") if "competition_type" in df.columns else [],
        },
        "requests_by_rejection_reason": {
            "label": "Number of rejections by reason",
            "data": _summarize_rejection_reasons(rejected_df, "requests_count"),
        },
    }

    payload = {
        "filter": {
            "customer_type": customer_type or "all",
            "year": year or "all",
        },
        "unit": "count",
        "available_years": available_years,
        "start_year": min(available_years) if available_years else None,
        "charts": charts,
        "monthly_requests": monthly_totals,
        "monthly_rejections_by_reason": _monthly_rejection_breakdown(rejected_df, "requests_count"),
        "total_requests": total_requests,
        "total_rejections": total_rejections,
    }

    if status.get("status") == "stale":
        age_days = status.get("age_days")
        age_text = str(int(age_days)) if isinstance(age_days, (int, float)) else "an unknown number of"
        payload["note"] = (
            f"Data file is old ({age_text} days). Upload a fresh file for the latest readings."
        )

    return payload


def to_excel(payload: Dict) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_rows = [
            {"metric": "customer_type", "value": payload.get("filter", {}).get("customer_type")},
            {"metric": "year", "value": payload.get("filter", {}).get("year")},
            {"metric": "total_requests", "value": payload.get("total_requests")},
            {"metric": "total_rejections", "value": payload.get("total_rejections")},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        pd.DataFrame(payload.get("monthly_requests", [])).to_excel(writer, sheet_name="Monthly", index=False)
        pd.DataFrame(payload.get("monthly_rejections_by_reason", [])).to_excel(
            writer,
            sheet_name="Monthly_Rejections",
            index=False,
        )

        for key, chart in payload.get("charts", {}).items():
            data = chart.get("data") or []
            if not data:
                continue
            pd.DataFrame(data).to_excel(writer, sheet_name=key, index=False)
    buffer.seek(0)
    return buffer.getvalue()
