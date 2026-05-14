# app/services/distributor_responses_service.py
"""
Delivery 2 – Endpoints 12, 13, 14
Source: Files_Netunei_hashmal_my_teshuvotmehalek.csv (Distributor Responses)

Provides:
  - Response capacity divided by period
  - Response capacity divided by facility size (kW)
  - Response capacity divided by district
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from fastapi import HTTPException

from app.services.data_file_manager import ensure_fresh_data_file
from app.services.csv_downloader_service import ensure_fresh_or_download
from app.utils.enums import DataFileSource

# Hebrew → English column mapping
_COL_MAP = {
    "מחוז": "district",
    "מעמד מוניצפלי": "municipal_status",
    "מעמד מוניציפלי": "municipal_status",
    "מועצה/ עירייה": "council_city",
    "יישוב": "locality",
    "סמל יישוב": "locality_code",
    "ביטולים": "cancellations",
    "טכנולוגיה": "technology",
    "סיווג  של הטכנולוגיה": "technology_classification",
    "סיווג של הטכנולוגיה": "technology_classification",
    "תשובת מחלק": "distributor_response",
    "שם הסדרה": "regulation_name",
    "תאריך תשובת מחלק": "response_date",
    "הספק MW": "capacity_mw",
}

# Hebrew → English value translations
_DISTRICT_MAP = {
    "ירושלים": "Jerusalem",
    "הצפון": "North",
    "הדרום": "South",
    "חיפה": "Haifa",
    "המרכז": "Center",
    'יו"ש': "Judea & Samaria",
    'ת"א': "Tel Aviv",
    "אחר": "Other",
}

_TECHNOLOGY_MAP = {
    "פוטוולטאי": "Photovoltaic",
    "רוח": "Wind",
    "אחר": "Other",
}

_TECH_CLASS_MAP = {
    "פוטוולטאי": "Photovoltaic",
    "משולב אגירה": "Integrated Storage",
    "גלי ים": "Wave Energy",
    "רוח": "Wind",
    "דו שימושי": "Dual Use",
    "אגרו-וולטאי": "Agro-Voltaic",
    "קרקעי": "Ground-mounted",
    "ביוגז": "Biogas",
}

_RESPONSE_MAP = {
    "חיובית": "Positive",
    "חיובית חלקית": "Partial Positive",
    "חיובית מוגבלת": "Limited Positive",
    "שלילית": "Negative",
}

_CANCELLATION_MAP = {
    "הזמנות לא מבוטלות": "Non-cancelled",
    "הזמנות  מבוטלות": "Cancelled",
    "הזמנות מבוטלות": "Cancelled",
}

_MUNICIPAL_STATUS_MAP = {
    "מועצה מקומית": "Local Council",
    "מועצה אזורית": "Regional Council",
    "עירייה": "City",
    "אחר": "Other",
}

# Capacity size brackets (MW) used for endpoint 13
# Ranges are non-overlapping: boundary values fall into the HIGHER bracket.
# e.g. exactly 0.016 MW (16 kW) goes into "17–50 kW", not "Up to 16 kW".
_SIZE_BRACKETS_MW = [
    (0,     0.016,         "Up to 16 kW"),
    (0.016, 0.050,         "17–50 kW"),
    (0.050, 0.200,         "51–200 kW"),
    (0.200, 1.0,           "201 kW–1 MW"),
    (1.0,   5.0,           "1–5 MW"),
    (5.0,   50.0,          "5–50 MW"),
    (50.0,  float("inf"),  "50+ MW"),
]


def _assign_size_bracket(capacity_mw: float) -> str:
    """Assign a human-readable size category based on capacity in MW.
    Brackets are non-overlapping and cover the full range with no gaps:
    first bracket includes both endpoints (0 ≤ x ≤ high); subsequent
    brackets are (low, high] (exclusive low, inclusive high).
    """
    for i, (low, high, label) in enumerate(_SIZE_BRACKETS_MW):
        if i == 0:
            if 0 <= capacity_mw <= high:
                return label
        else:
            if low < capacity_mw <= high:
                return label
    return "Unknown"


class DistributorResponsesService:
    """
    Service for Delivery 2 endpoints based on the distributor-responses CSV.
    """

    @staticmethod
    def _load_dataframe(csv_path: Optional[Path] = None) -> pd.DataFrame:
        csv_path = csv_path or ensure_fresh_or_download(DataFileSource.DISTRIBUTOR_RESPONSES)
        df: Optional[pd.DataFrame] = None
        for enc in ("cp1255", "utf-8-sig", "latin1"):
            try:
                df = pd.read_csv(csv_path, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise HTTPException(status_code=424, detail="Unable to load distributor-responses CSV.")

        # Clean and rename columns
        df.columns = [col.replace("\ufeff", "").strip() for col in df.columns]
        rename_map = {}
        for col in df.columns:
            if col in _COL_MAP:
                rename_map[col] = _COL_MAP[col]
        df = df.rename(columns=rename_map)

        # Parse response date
        if "response_date" in df.columns:
            df["date"] = pd.to_datetime(
                df["response_date"], format="%d/%m/%Y %H:%M", errors="coerce",
            )
            # Fallback to other formats
            mask = df["date"].isna()
            if mask.any():
                df.loc[mask, "date"] = pd.to_datetime(
                    df.loc[mask, "response_date"], errors="coerce",
                )
            df = df.dropna(subset=["date"])
        else:
            raise HTTPException(
                status_code=424,
                detail="CSV missing required column: response_date",
            )

        # Parse capacity
        if "capacity_mw" in df.columns:
            df["capacity_mw"] = pd.to_numeric(df["capacity_mw"], errors="coerce").fillna(0)
        else:
            raise HTTPException(status_code=424, detail="CSV missing required column: capacity_mw")

        # Translate values
        if "district" in df.columns:
            df["district"] = df["district"].map(_DISTRICT_MAP).fillna(df["district"])
        if "technology" in df.columns:
            df["technology"] = df["technology"].map(_TECHNOLOGY_MAP).fillna(df["technology"])
        if "technology_classification" in df.columns:
            df["technology_classification"] = (
                df["technology_classification"].map(_TECH_CLASS_MAP).fillna(df["technology_classification"])
            )
        if "distributor_response" in df.columns:
            df["distributor_response"] = (
                df["distributor_response"].map(_RESPONSE_MAP).fillna(df["distributor_response"])
            )
        if "cancellations" in df.columns:
            df["cancellations"] = (
                df["cancellations"].map(_CANCELLATION_MAP).fillna(df["cancellations"])
            )
        if "municipal_status" in df.columns:
            df["municipal_status"] = (
                df["municipal_status"].map(_MUNICIPAL_STATUS_MAP).fillna(df["municipal_status"])
            )

        # Assign size bracket
        df["size_bracket"] = df["capacity_mw"].apply(_assign_size_bracket)

        # Sort by date
        df = df.sort_values("date").reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Endpoint 12 – Response Capacity by Period
    # ------------------------------------------------------------------
    @staticmethod
    def get_response_capacity_by_period(
        year: Optional[int] = None,
        district: Optional[str] = None,
        technology: Optional[str] = None,
        response_type: Optional[str] = None,
        include_cancelled: bool = False,
    ) -> Dict:
        """
        Delivery 2 – Endpoint 12 (Row 19):
        Response capacity divided by time period.
        """
        df = DistributorResponsesService._load_dataframe()

        # Filter out cancelled orders by default
        if not include_cancelled and "cancellations" in df.columns:
            df = df[df["cancellations"] == "Non-cancelled"]

        if district:
            df = df[df["district"].str.lower() == district.lower()]
        if technology:
            df = df[df["technology"].str.lower() == technology.lower()]
        if response_type:
            df = df[df["distributor_response"].str.lower() == response_type.lower()]

        # Aggregate by month
        df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

        if year:
            df = df[df["date"].dt.year == year]

        monthly = (
            df.groupby("month")
            .agg(
                total_mw=("capacity_mw", "sum"),
                request_count=("capacity_mw", "count"),
            )
            .reset_index()
            .sort_values("month")
        )

        series = [
            {
                "period": row["month"].strftime("%Y-%m"),
                "total_mw": round(row["total_mw"], 3),
                "request_count": int(row["request_count"]),
            }
            for _, row in monthly.iterrows()
        ]

        # Response type breakdown
        response_breakdown = (
            df.groupby("distributor_response")
            .agg(total_mw=("capacity_mw", "sum"), count=("capacity_mw", "count"))
            .reset_index()
        )
        response_summary = {
            row["distributor_response"]: {
                "total_mw": round(row["total_mw"], 3),
                "count": int(row["count"]),
            }
            for _, row in response_breakdown.iterrows()
        }

        return {
            "title": "Response Capacity Divided by Period",
            "title_he": "הספק תשובות מחלק לפי תקופה",
            "total_mw": round(df["capacity_mw"].sum(), 3),
            "total_requests": len(df),
            "filters_applied": {
                "year": year,
                "district": district,
                "technology": technology,
                "response_type": response_type,
                "include_cancelled": include_cancelled,
            },
            "series": series,
            "response_type_breakdown": response_summary,
        }

    # ------------------------------------------------------------------
    # Endpoint 13 – Response Capacity by Facility Size (kW)
    # ------------------------------------------------------------------
    @staticmethod
    def get_response_capacity_by_size(
        year: Optional[int] = None,
        district: Optional[str] = None,
        response_type: Optional[str] = "Positive",
        include_cancelled: bool = False,
    ) -> Dict:
        """
        Delivery 2 – Endpoint 13 (Row 20):
        Response capacity divided by facility size in kilowatts.
        Defaults to Positive responses only (client requirement for Diagram 5.2).
        """
        df = DistributorResponsesService._load_dataframe()

        if not include_cancelled and "cancellations" in df.columns:
            df = df[df["cancellations"] == "Non-cancelled"]
        if district:
            df = df[df["district"].str.lower() == district.lower()]
        if response_type:
            df = df[df["distributor_response"].str.lower() == response_type.lower()]
        if year:
            df = df[df["date"].dt.year == year]


        grouped = (
            df.groupby("size_bracket")
            .agg(
                total_mw=("capacity_mw", "sum"),
                request_count=("capacity_mw", "count"),
            )
            .reset_index()
        )

        # Preserve bracket order
        bracket_order = [label for _, _, label in _SIZE_BRACKETS_MW]
        grouped["_order"] = grouped["size_bracket"].apply(
            lambda x: bracket_order.index(x) if x in bracket_order else len(bracket_order)
        )
        grouped = grouped.sort_values("_order")

        series = [
            {
                "size_bracket": row["size_bracket"],
                "total_mw": round(row["total_mw"], 3),
                "request_count": int(row["request_count"]),
            }
            for _, row in grouped.iterrows()
        ]

        # Also breakdown by year + size for time-series view
        df["year_val"] = df["date"].dt.year
        yearly_size = (
            df.groupby(["year_val", "size_bracket"])
            .agg(total_mw=("capacity_mw", "sum"), count=("capacity_mw", "count"))
            .reset_index()
        )
        yearly_series = []
        for yr, grp in yearly_size.groupby("year_val"):
            brackets = {}
            for _, row in grp.iterrows():
                brackets[row["size_bracket"]] = {
                    "total_mw": round(row["total_mw"], 3),
                    "count": int(row["count"]),
                }
            yearly_series.append({"year": int(yr), "size_brackets": brackets})

        return {
            "title": "Response Capacity Divided by Facility Size (Kilowatt)",
            "title_he": "הספק תשובת מחולק לפי גודל מתקן (קילוואט)",
            "total_mw": round(df["capacity_mw"].sum(), 3),
            "total_requests": len(df),
            "filters_applied": {
                "year": year,
                "district": district,
                "include_cancelled": include_cancelled,
            },
            "size_bracket_definitions": [
                {"label": label, "min_mw": low, "max_mw": high if high != float("inf") else None}
                for low, high, label in _SIZE_BRACKETS_MW
            ],
            "series": series,
            "yearly_series": yearly_series,
        }

    # ------------------------------------------------------------------
    # Endpoint 14 – Response Capacity by District
    # ------------------------------------------------------------------
    @staticmethod
    def get_response_capacity_by_district(
        year: Optional[int] = None,
        technology: Optional[str] = None,
        include_cancelled: bool = True,
    ) -> Dict:
        """
        Delivery 2 – Endpoint 14 (Row 21):
        Response capacity divided by district.

        Default includes every row in the source file so per-region totals
        match what a manual sum of the mehubarim CSV produces; pass
        include_cancelled=False to exclude cancelled orders.
        """
        df = DistributorResponsesService._load_dataframe()

        if not include_cancelled and "cancellations" in df.columns:
            df = df[df["cancellations"] == "Non-cancelled"]
        if technology:
            df = df[df["technology"].str.lower() == technology.lower()]
        if year:
            df = df[df["date"].dt.year == year]

        grouped = (
            df.groupby("district")
            .agg(
                total_mw=("capacity_mw", "sum"),
                request_count=("capacity_mw", "count"),
            )
            .reset_index()
            .sort_values("total_mw", ascending=False)
        )

        series = [
            {
                "district": row["district"],
                "total_mw": round(row["total_mw"], 3),
                "request_count": int(row["request_count"]),
            }
            for _, row in grouped.iterrows()
        ]

        # Technology breakdown per district
        district_tech = (
            df.groupby(["district", "technology"])["capacity_mw"]
            .sum()
            .reset_index()
        )
        breakdown = {}
        for dist, grp in district_tech.groupby("district"):
            breakdown[dist] = {
                row["technology"]: round(row["capacity_mw"], 3)
                for _, row in grp.iterrows()
            }

        return {
            "title": "Response Capacity Divided by District",
            "title_he": "הספק תשובת מחולק לפי מחוז",
            "total_mw": round(df["capacity_mw"].sum(), 3),
            "total_requests": len(df),
            "filters_applied": {
                "year": year,
                "technology": technology,
                "include_cancelled": include_cancelled,
            },
            "series": series,
            "district_technology_breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Excel export helper
    # ------------------------------------------------------------------
    @staticmethod
    def to_excel(payload: Dict) -> bytes:
        """Build an Excel workbook from any of the distributor-responses endpoints."""
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            if "series" in payload:
                series_data = payload["series"]
                if series_data and "size_brackets" not in series_data[0]:
                    pd.DataFrame(series_data).to_excel(writer, sheet_name="Series", index=False)

            if "response_type_breakdown" in payload:
                rows = [
                    {"Response Type": k, "Total MW": v["total_mw"], "Count": v["count"]}
                    for k, v in payload["response_type_breakdown"].items()
                ]
                pd.DataFrame(rows).to_excel(writer, sheet_name="Response Breakdown", index=False)

            if "yearly_series" in payload:
                rows = []
                for entry in payload["yearly_series"]:
                    for bracket, vals in entry.get("size_brackets", {}).items():
                        rows.append({
                            "Year": entry["year"],
                            "Size Bracket": bracket,
                            "Total MW": vals["total_mw"],
                            "Count": vals["count"],
                        })
                if rows:
                    pd.DataFrame(rows).to_excel(writer, sheet_name="By Size & Year", index=False)

            if "district_technology_breakdown" in payload:
                rows = []
                for dist, techs in payload["district_technology_breakdown"].items():
                    for tech, mw in techs.items():
                        rows.append({"District": dist, "Technology": tech, "MW": mw})
                if rows:
                    pd.DataFrame(rows).to_excel(writer, sheet_name="District x Technology", index=False)

        buffer.seek(0)
        return buffer.getvalue()
