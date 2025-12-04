from datetime import datetime, timedelta
from fastapi import HTTPException

# Accepted input formats for query parameters.
ACCEPTED_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%m-%Y")


def parse_date(value: str) -> datetime:
    """
    Parse a date string using supported formats.
    Raises HTTPException with 400 on invalid input.
    """
    for fmt in ACCEPTED_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            # If only month/year provided, normalize to first of month.
            if fmt == "%m-%Y":
                dt = dt.replace(day=1)
            return dt
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail="Invalid date format. Use YYYY-MM-DD or DD-MM-YYYY.",
    )


def resolve_date_range(start_date: str | None, end_date: str | None, default_days: int = 365) -> tuple[datetime, datetime]:
    """
    Resolve a date range using provided query params or a default window.
    Ensures start_date <= end_date and returns datetime objects.
    """
    today = datetime.today()
    if not start_date or not end_date:
        start_dt = today - timedelta(days=default_days)
        end_dt = today
    else:
        start_dt = parse_date(start_date)
        end_dt = parse_date(end_date)

    if start_dt > end_dt:
        raise HTTPException(
            status_code=400,
            detail="start_date must be earlier than or equal to end_date.",
        )

    return start_dt, end_dt


def to_noga_date(value: datetime) -> str:
    """Format datetime for the NOGA API (dd-mm-YYYY)."""
    return value.strftime("%d-%m-%Y")


def to_iso_date(value: datetime) -> str:
    """Format datetime for API responses (YYYY-MM-DD)."""
    return value.strftime("%Y-%m-%d")
