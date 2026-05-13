from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from fastapi import HTTPException

from app.services.csv_downloader_service import ensure_fresh_ims_weather_file
from app.services.noga_service import NogaService
from app.services.noga_source_mode import use_nzo_fallback_only
from app.services.nzo_fallback_service import NZO_TIME_RESOLUTION_FIELD
from app.services.renewable_transition_service import TOTAL_GENERATION_KEYS
from app.utils.date_utils import to_noga_date
from app.utils.enums import DataFileSource

logger = logging.getLogger(__name__)


class HeatLoadView(str, Enum):
    MONTH = "month"  # ticks by days
    YEAR = "year"    # ticks by weeks
    CUSTOM = "custom"


@dataclass
class HeatLoadResult:
    payload: Dict
    weather_for_export: pd.DataFrame


STATION_ALIASES = {
    "tel_aviv_coast": [
        "tel aviv - coast",
        "tel aviv coast",
        "tel aviv, coast",
        "תל-אביב, חוף",
        "תל אביב, חוף",
        "תל אביב חוף",
    ],
    "jerusalem_center": [
        "jerusalem - center",
        "jerusalem center",
        "jerusalem, center",
        "ירושלים, מרכז",
        "ירושלים מרכז",
    ],
    "jerusalem_givat_ram": [
        "jerusalem - givat ram",
        "jerusalem givat ram",
        "jerusalem, givat ram",
        "ירושלים, גבעת רם",
        "ירושלים גבעת רם",
    ],
}

STATION_LABELS = {
    "tel_aviv_coast": "Tel Aviv - Coast",
    "jerusalem_center": "Jerusalem - Center",
    "jerusalem_givat_ram": "Jerusalem - Givat Ram",
}

THI_FORMULA_TEXT = "THI = T - (0.55 - 0.0055*RH) * (T - 14.5)"
WEATHER_DEFAULT_DAYS = int(os.getenv("HEAT_LOAD_DEFAULT_DAYS", "365"))


class HeatLoadVsGenerationService:
    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def _resolve_csv_path(start_dt: datetime, end_dt: datetime) -> Path:
        override = os.getenv("HEAT_LOAD_CSV_PATH")
        if override:
            path = Path(override)
            if path.exists():
                return path
            raise HTTPException(
                status_code=424,
                detail=f"HEAT_LOAD_CSV_PATH is set but file was not found: {path}",
            )

        try:
            return ensure_fresh_ims_weather_file(start_dt, end_dt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("IMS weather auto-refresh failed, falling back to local data_*.csv: %s", exc)

        root = HeatLoadVsGenerationService._project_root()
        candidates = sorted(root.glob("data_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            candidates = sorted(
                (root / "data_files").glob("data_*.csv"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        if not candidates:
            raise HTTPException(
                status_code=428,
                detail=(
                    "Heat load source CSV is missing. Configure IMS_TOKEN and trigger "
                    "/api/v1/data-files/fetch-ims-weather, or add a file named like "
                    "'data_*.csv' to the project root (or data_files), or configure "
                    "HEAT_LOAD_CSV_PATH."
                ),
            )
        return candidates[0]

    @staticmethod
    def _normalize_station_name(value: str) -> str:
        text = str(value or "").strip().lower()
        for token in [",", "-", "_", "  "]:
            text = text.replace(token, " ")
        return " ".join(text.split())

    @staticmethod
    def _allowed_station_lookup() -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for canonical, aliases in STATION_ALIASES.items():
            for alias in aliases:
                lookup[HeatLoadVsGenerationService._normalize_station_name(alias)] = canonical
        return lookup

    @staticmethod
    def _find_column(columns, tokens: List[str], fallback_index: int) -> str | None:
        normalized_tokens = [
            HeatLoadVsGenerationService._normalize_station_name(token)
            for token in tokens
        ]
        for column in columns:
            normalized_column = HeatLoadVsGenerationService._normalize_station_name(str(column))
            if any(token and token in normalized_column for token in normalized_tokens):
                return column
        if len(columns) > fallback_index:
            return columns[fallback_index]
        return None

    @staticmethod
    def _load_weather_dataframe(start_dt: datetime, end_dt: datetime) -> Tuple[pd.DataFrame, List[str]]:
        csv_path = HeatLoadVsGenerationService._resolve_csv_path(start_dt, end_dt)
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="latin1")

        station_col = HeatLoadVsGenerationService._find_column(
            df.columns,
            ["station", "תחנה"],
            fallback_index=0,
        )
        timestamp_col = HeatLoadVsGenerationService._find_column(
            df.columns,
            ["date", "time", "תאריך", "שעה"],
            fallback_index=1,
        )
        humidity_col = HeatLoadVsGenerationService._find_column(
            df.columns,
            ["humidity", "relative", "לחות"],
            fallback_index=2,
        )
        temperature_col = HeatLoadVsGenerationService._find_column(
            df.columns,
            ["temperature", "temp", "טמפרטורה"],
            fallback_index=3,
        )
        missing = [
            name
            for name, column in {
                "station": station_col,
                "timestamp": timestamp_col,
                "relative_humidity": humidity_col,
                "temperature_c": temperature_col,
            }.items()
            if column is None
        ]
        if missing:
            raise HTTPException(
                status_code=424,
                detail=f"Heat load CSV format is invalid. Could not identify columns: {missing}",
            )

        weather = df.rename(
            columns={
                station_col: "station_raw",
                timestamp_col: "timestamp_utc",
                humidity_col: "relative_humidity",
                temperature_col: "temperature_c",
            }
        ).copy()

        weather["timestamp_utc"] = pd.to_datetime(
            weather["timestamp_utc"],
            format="%d/%m/%Y %H:%M",
            errors="coerce",
        )
        weather["relative_humidity"] = pd.to_numeric(weather["relative_humidity"], errors="coerce")
        weather["temperature_c"] = pd.to_numeric(weather["temperature_c"], errors="coerce")
        weather = weather.dropna(subset=["timestamp_utc", "relative_humidity", "temperature_c", "station_raw"])

        station_lookup = HeatLoadVsGenerationService._allowed_station_lookup()
        weather["station_normalized"] = weather["station_raw"].apply(HeatLoadVsGenerationService._normalize_station_name)
        weather["station_key"] = weather["station_normalized"].map(station_lookup)
        weather = weather.dropna(subset=["station_key"])

        weather = weather[(weather["timestamp_utc"] >= start_dt) & (weather["timestamp_utc"] <= end_dt)]
        if weather.empty:
            raise HTTPException(
                status_code=404,
                detail="No heat load data found for the selected period.",
            )

        # THI heat load formula combining temperature and relative humidity.
        weather["heat_load"] = weather["temperature_c"] - (
            (0.55 - 0.0055 * weather["relative_humidity"]) * (weather["temperature_c"] - 14.5)
        )

        present_keys = set(weather["station_key"].dropna().tolist())
        missing_station_labels = [
            STATION_LABELS[key]
            for key in STATION_LABELS.keys()
            if key not in present_keys
        ]

        weather["station"] = weather["station_key"].map(STATION_LABELS)
        return weather, missing_station_labels

    @staticmethod
    async def _fetch_generation_dataframe(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        token = os.getenv("NOGA_API_TOKEN")
        if not token and not use_nzo_fallback_only():
            raise HTTPException(status_code=424, detail="NOGA_API_TOKEN is not configured.")

        raw_values = await NogaService.fetch_production_mix(
            to_noga_date(start_dt),
            to_noga_date(end_dt),
            token,
        )

        rows: List[Dict] = []
        for sample in raw_values:
            date = sample.get("date")
            time = sample.get("time")
            if not date or not time:
                continue
            ts = None
            for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"):
                try:
                    ts = datetime.strptime(f"{date} {time}", fmt)
                    break
                except ValueError:
                    continue
            if ts is None:
                continue
            if ts < start_dt or ts > end_dt:
                continue

            total_generation = sum(
                float(sample.get(key, 0) or 0)
                for key in TOTAL_GENERATION_KEYS
            )
            if sample.get(NZO_TIME_RESOLUTION_FIELD) == "hour":
                total_generation /= 12
            rows.append({"timestamp": ts, "electricity_generation_mw": total_generation})

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No generation data found for the selected period.",
            )

        gen_df = pd.DataFrame(rows)
        gen_df = gen_df.sort_values("timestamp")
        return gen_df

    @staticmethod
    def _bucket_by_view(df: pd.DataFrame, ts_col: str, value_col: str, view: HeatLoadView) -> pd.DataFrame:
        data = df.copy()
        if view == HeatLoadView.YEAR:
            data["period"] = data[ts_col].dt.to_period("W").astype(str)
            data["label"] = data[ts_col].dt.to_period("W").apply(lambda p: p.start_time.strftime("%d %b"))
        else:
            data["period"] = data[ts_col].dt.strftime("%Y-%m-%d")
            data["label"] = data[ts_col].dt.strftime("%d %b")

        grouped = (
            data.groupby(["period", "label"], as_index=False)[value_col]
            .mean()
            .rename(columns={value_col: value_col})
        )
        return grouped.sort_values("period")

    @staticmethod
    async def get_data(start_dt: datetime, end_dt: datetime, view: HeatLoadView) -> HeatLoadResult:
        weather_df, missing_station_labels = HeatLoadVsGenerationService._load_weather_dataframe(start_dt, end_dt)

        weather_bucket = HeatLoadVsGenerationService._bucket_by_view(
            weather_df,
            ts_col="timestamp_utc",
            value_col="heat_load",
            view=view,
        )

        generation_note = None
        generation_bucket = pd.DataFrame(columns=["period", "label", "electricity_generation_mw"])
        try:
            generation_df = await HeatLoadVsGenerationService._fetch_generation_dataframe(start_dt, end_dt)
            generation_bucket = HeatLoadVsGenerationService._bucket_by_view(
                generation_df,
                ts_col="timestamp",
                value_col="electricity_generation_mw",
                view=view,
            )
        except Exception as exc:  # noqa: BLE001
            generation_note = f"Generation data is unavailable: {exc}"

        if {"period", "electricity_generation_mw"}.issubset(generation_bucket.columns):
            generation_for_merge = generation_bucket[["period", "electricity_generation_mw"]]
        else:
            generation_for_merge = pd.DataFrame(columns=["period", "electricity_generation_mw"])

        merged = pd.merge(
            weather_bucket,
            generation_for_merge,
            on="period",
            how="left",
        )
        merged["label"] = merged["label"].fillna("")
        merged = merged.sort_values("period")

        series = []
        for _, row in merged.iterrows():
            generation_value = row.get("electricity_generation_mw")
            series.append(
                {
                    "period": row["period"],
                    "label": row["label"],
                    "heat_load": round(float(row["heat_load"]), 2),
                    "electricity_generation_mw": (
                        round(float(generation_value), 2)
                        if pd.notna(generation_value)
                        else None
                    ),
                }
            )

        notes: List[str] = []
        if missing_station_labels:
            notes.append(
                "Missing configured stations in source file: " + ", ".join(missing_station_labels)
            )
        if generation_note:
            notes.append(generation_note)

        payload = {
            "view": view.value,
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
            "units": {
                "heat_load": "THI",
                "electricity_generation": "MW",
            },
            "series": series,
        }
        if notes:
            payload["note"] = "; ".join(notes)

        export_df = weather_df[["station", "timestamp_utc", "relative_humidity", "temperature_c"]].copy()
        export_df = export_df.sort_values(["timestamp_utc", "station"]).reset_index(drop=True)
        export_df["heat_load_formula"] = ""
        for idx in range(len(export_df)):
            row_no = idx + 2  # Excel rows start at 1, with header row at 1.
            export_df.at[idx, "heat_load_formula"] = f"=D{row_no}-(0.55-0.0055*C{row_no})*(D{row_no}-14.5)"
        export_df["heat_load_value"] = weather_df.sort_values(["timestamp_utc", "station"])["heat_load"].round(2).values

        return HeatLoadResult(payload=payload, weather_for_export=export_df)

    @staticmethod
    def to_excel_bytes(result: HeatLoadResult) -> bytes:
        buffer = BytesIO()
        payload = result.payload

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            summary_rows = [
                {"metric": "view", "value": payload.get("view")},
                {"metric": "start_date", "value": payload.get("start_date")},
                {"metric": "end_date", "value": payload.get("end_date")},
                {
                    "metric": "source_file",
                    "value": HeatLoadVsGenerationService._resolve_csv_path(
                        datetime.fromisoformat(payload.get("start_date")),
                        datetime.fromisoformat(payload.get("end_date")),
                    ).name,
                },
                {"metric": "heat_load_formula", "value": THI_FORMULA_TEXT},
                {"metric": "stations_configured", "value": ", ".join(STATION_LABELS.values())},
                {"metric": "note", "value": payload.get("note")},
            ]
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
            pd.DataFrame(payload.get("series", [])).to_excel(writer, sheet_name="Series", index=False)
            result.weather_for_export.to_excel(writer, sheet_name="RawWeather", index=False)

        buffer.seek(0)
        return buffer.getvalue()
