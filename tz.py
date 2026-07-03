"""Dual-timezone helpers (non-negotiable for FTDC correlation).

Every timestamp the app records carries BOTH UTC (matches FTDC) and IST (what
the operator reads). UTC is always the source of truth internally.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import OPERATOR_TZ

_IST = ZoneInfo(OPERATOR_TZ)


def now_utc() -> datetime:
    """Timezone-aware 'now' in UTC."""
    return datetime.now(timezone.utc)


def to_ist(dt: datetime) -> datetime:
    """Convert an aware datetime to IST (assumes UTC if naive)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_IST)


def iso_utc(dt: datetime | None = None) -> str:
    dt = dt or now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def iso_ist(dt: datetime | None = None) -> str:
    dt = dt or now_utc()
    return to_ist(dt).isoformat()


def dual(dt: datetime | None = None) -> dict:
    """Return a {'utc': ..., 'ist': ...} pair for a moment in time."""
    dt = dt or now_utc()
    return {"utc": iso_utc(dt), "ist": iso_ist(dt)}


def stamp_for_path(dt: datetime | None = None) -> str:
    """Filesystem-safe UTC timestamp for run subfolders, e.g. 20260624T043000Z."""
    dt = dt or now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
