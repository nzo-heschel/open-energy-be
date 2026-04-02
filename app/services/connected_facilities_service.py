# app/services/connected_facilities_service.py
"""
Delivery 2 – Endpoints 9, 10, 11
Source: Files_Netunei_hashmal_my_mehubarim.csv (Connected Facilities)

Provides:
  - Installed capacity (cumulative) of renewable energy facilities
  - Installed capacity growth rate
  - Facility capacity connected over time by facility size
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
    "מעמד מוניציפלי": "municipal_status",
    "מועצה/ עירייה": "council_city",
    "יישוב": "locality",
    "סמל יישוב": "locality_code",
    "טכנולוגיה": "technology",
    "סיווג  של הטכנולוגיה": "technology_classification",
    "סיווג של הטכנולוגיה": "technology_classification",
    "שם הסדרה": "regulation_name",
    "מועד הפעלה מסחרית בפועל": "commercial_operation_date",
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
    "תרמו סולאר": "Solar Thermal",
    "אחר": "Other",
}

_TECH_CLASS_MAP = {
    "דו שימושי": "Dual Use",
    "קרקעי": "Ground-mounted",
    "משולב אגירה": "Integrated Storage",
    "רוח": "Wind",
    "מגדל שמש": "Solar Tower",
    "שוקת פרבולית": "Parabolic Trough",
    "ביוגז": "Biogas",
    "פוטוולטאי": "Photovoltaic",
    "הידרו אלקטרי": "Hydroelectric",
    "מטמנות": "Landfill Gas",
    "גלי ים": "Wave Energy",
}

_MUNICIPAL_STATUS_MAP = {
    "מועצה מקומית": "Local Council",
    "מועצה אזורית": "Regional Council",
    "עירייה": "City",
    "אחר": "Other",
}

# Capacity size brackets (MW) used for endpoint 11
# Ranges are non-overlapping: boundary values fall into the HIGHER bracket.
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
    Lower bound is exclusive, upper bound is inclusive (except the first bracket).
    """
    for i, (low, high, label) in enumerate(_SIZE_BRACKETS_MW):
        if i == 0:
            if 0 <= capacity_mw <= low + (high - low) - 0.000001:
                return label
        else:
            if low < capacity_mw <= high:
                return label
    return "Unknown"


class ConnectedFacilitiesService:
    """
    Service for Delivery 2 endpoints based on the connected-facilities CSV.
    """

    @staticmethod
    def _load_dataframe(csv_path: Optional[Path] = None) -> pd.DataFrame:
        csv_path = csv_path or ensure_fresh_or_download(DataFileSource.CONNECTED_FACILITIES)
        df: Optional[pd.DataFrame] = None
        for enc in ("cp1255", "utf-8-sig", "latin1"):
            try:
                df = pd.read_csv(csv_path, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise HTTPException(status_code=424, detail="Unable to load connected-facilities CSV.")

        # Clean and rename columns
        df.columns = [col.replace("\ufeff", "").strip() for col in df.columns]
        rename_map = {}
        for col in df.columns:
            if col in _COL_MAP:
                rename_map[col] = _COL_MAP[col]
        df = df.rename(columns=rename_map)

        # Parse date
        if "commercial_operation_date" in df.columns:
            df["date"] = pd.to_datetime(
                df["commercial_operation_date"], format="%d/%m/%Y", errors="coerce",
            )
            df = df.dropna(subset=["date"])
        else:
            raise HTTPException(
                status_code=424,
                detail="CSV missing required column: commercial_operation_date",
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
    # Endpoint 9 – Installed Capacity (Cumulative)
    # ------------------------------------------------------------------
    @staticmethod
    def get_installed_capacity(
        year: Optional[int] = None,
        district: Optional[str] = None,
        technology: Optional[str] = None,
    ) -> Dict:
        """
        Delivery 2 – Endpoint 9 (Row 16):
        Cumulative installed capacity of renewable energy facilities over time.
        """
        df = ConnectedFacilitiesService._load_dataframe()

        if district:
            df = df[df["district"].str.lower() == district.lower()]
        if technology:
            df = df[df["technology"].str.lower() == technology.lower()]

        # Aggregate by month
        df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
        monthly = (
            df.groupby("month")["capacity_mw"]
            .sum()
            .reset_index()
            .sort_values("month")
        )
        monthly["cumulative_mw"] = monthly["capacity_mw"].cumsum()

        # Optionally filter to a specific year for display
        if year:
            monthly = monthly[monthly["month"].dt.year <= year]

        series = [
            {
                "period": row["month"].strftime("%Y-%m"),
                "added_mw": round(row["capacity_mw"], 3),
                "cumulative_mw": round(row["cumulative_mw"], 3),
            }
            for _, row in monthly.iterrows()
        ]

        # Breakdown by technology
        tech_breakdown = (
            df.groupby("technology")["capacity_mw"]
            .sum()
            .round(3)
            .to_dict()
        )

        # Breakdown by district
        district_breakdown = (
            df.groupby("district")["capacity_mw"]
            .sum()
            .round(3)
            .to_dict()
        )

        total_mw = round(df["capacity_mw"].sum(), 3)

        return {
            "title": "Installed Capacity (Cumulative) of Renewable Energy Facilities",
            "title_he": "הספק מותקן (מצטבר) של מתקנים לייצור אנרגיות מתחדשות",
            "total_installed_mw": total_mw,
            "total_facilities": len(df),
            "filters_applied": {
                "year": year,
                "district": district,
                "technology": technology,
            },
            "series": series,
            "technology_breakdown": tech_breakdown,
            "district_breakdown": district_breakdown,
            "display": "Table",
        }

    # ------------------------------------------------------------------
    # Endpoint 10 – Installed Capacity Growth Rate
    # ------------------------------------------------------------------
    @staticmethod
    def get_installed_capacity_growth(
        district: Optional[str] = None,
        technology: Optional[str] = None,
    ) -> Dict:
        """
        Delivery 2 – Endpoint 10 (Row 17):
        Growth rate of cumulative installed capacity over time.
        """
        df = ConnectedFacilitiesService._load_dataframe()

        if district:
            df = df[df["district"].str.lower() == district.lower()]
        if technology:
            df = df[df["technology"].str.lower() == technology.lower()]

        # Aggregate by year
        df["year"] = df["date"].dt.year
        yearly = (
            df.groupby("year")["capacity_mw"]
            .sum()
            .reset_index()
            .sort_values("year")
        )
        yearly["cumulative_mw"] = yearly["capacity_mw"].cumsum()
        yearly["growth_rate_percent"] = yearly["capacity_mw"].pct_change() * 100

        series = [
            {
                "year": int(row["year"]),
                "added_mw": round(row["capacity_mw"], 3),
                "cumulative_mw": round(row["cumulative_mw"], 3),
                "growth_rate_percent": (
                    round(row["growth_rate_percent"], 2)
                    if pd.notna(row["growth_rate_percent"])
                    else None
                ),
            }
            for _, row in yearly.iterrows()
        ]

        return {
            "title": "Installed Capacity — Growth Rate",
            "title_he": "הספק מותקן (מצטבר) של מתקנים לייצור אנרגיות מתחדשות - קצב גדילה",
            "filters_applied": {
                "district": district,
                "technology": technology,
            },
            "series": series,
        }

    # ------------------------------------------------------------------
    # Endpoint 11 – Capacity Connected by Facility Size
    # ------------------------------------------------------------------
    @staticmethod
    def get_capacity_by_facility_size(
        year: Optional[int] = None,
        district: Optional[str] = None,
    ) -> Dict:
        """
        Delivery 2 – Endpoint 11 (Row 18):
        Facility capacity connected over time, by facility size.
        """
        df = ConnectedFacilitiesService._load_dataframe()

        if district:
            df = df[df["district"].str.lower() == district.lower()]

        # Aggregate by year + size bracket
        df["year"] = df["date"].dt.year
        if year:
            df = df[df["year"] <= year]

        grouped = (
            df.groupby(["year", "size_bracket"])["capacity_mw"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"sum": "total_mw", "count": "facility_count"})
        )

        # Pivot for series: each year has a breakdown by size
        series = []
        for yr, grp in grouped.groupby("year"):
            brackets = {}
            for _, row in grp.iterrows():
                brackets[row["size_bracket"]] = {
                    "total_mw": round(row["total_mw"], 3),
                    "facility_count": int(row["facility_count"]),
                }
            series.append({
                "year": int(yr),
                "size_brackets": brackets,
                "year_total_mw": round(grp["total_mw"].sum(), 3),
                "year_facility_count": int(grp["facility_count"].sum()),
            })

        # Overall totals by size bracket
        totals_by_size = (
            df.groupby("size_bracket")
            .agg(total_mw=("capacity_mw", "sum"), facility_count=("capacity_mw", "count"))
            .reset_index()
        )
        totals = {
            row["size_bracket"]: {
                "total_mw": round(row["total_mw"], 3),
                "facility_count": int(row["facility_count"]),
            }
            for _, row in totals_by_size.iterrows()
        }

        return {
            "title": "Facility Capacity Connected Over Time by Facility Size",
            "title_he": "הספק מתקנים שחוברו על ציר זמן, לפי גודל מתקן",
            "filters_applied": {
                "year": year,
                "district": district,
            },
            "size_bracket_definitions": [
                {"label": label, "min_mw": low, "max_mw": high if high != float("inf") else None}
                for low, high, label in _SIZE_BRACKETS_MW
            ],
            "series": series,
            "totals_by_size": totals,
        }

    # ------------------------------------------------------------------
    # Excel export helper
    # ------------------------------------------------------------------
    @staticmethod
    def to_excel(payload: Dict) -> bytes:
        """Build an Excel workbook from any of the connected-facilities endpoints."""
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            if "series" in payload:
                series_data = payload["series"]
                if series_data and "size_brackets" in series_data[0]:
                    # Endpoint 11 – flatten size brackets
                    rows = []
                    for entry in series_data:
                        for bracket, vals in entry.get("size_brackets", {}).items():
                            rows.append({
                                "Year": entry["year"],
                                "Size Bracket": bracket,
                                "Total MW": vals["total_mw"],
                                "Facility Count": vals["facility_count"],
                            })
                    pd.DataFrame(rows).to_excel(writer, sheet_name="Capacity by Size", index=False)
                else:
                    pd.DataFrame(series_data).to_excel(writer, sheet_name="Series", index=False)

            if "technology_breakdown" in payload:
                tech_df = pd.DataFrame(
                    [{"Technology": k, "MW": v} for k, v in payload["technology_breakdown"].items()]
                )
                tech_df.to_excel(writer, sheet_name="By Technology", index=False)

            if "district_breakdown" in payload:
                dist_df = pd.DataFrame(
                    [{"District": k, "MW": v} for k, v in payload["district_breakdown"].items()]
                )
                dist_df.to_excel(writer, sheet_name="By District", index=False)

            if "totals_by_size" in payload:
                size_df = pd.DataFrame(
                    [{"Size Bracket": k, "Total MW": v["total_mw"], "Count": v["facility_count"]}
                     for k, v in payload["totals_by_size"].items()]
                )
                size_df.to_excel(writer, sheet_name="Totals by Size", index=False)

        buffer.seek(0)
        return buffer.getvalue()
