from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or settings.TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    h, m = int(hour), int(minute)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Time must be between 00:00 and 23:59")
    return h, m


def _payday_in_month(year: int, month: int, day: int, hh: int, mm: int, tz: ZoneInfo) -> datetime:
    last = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last), hh, mm, tzinfo=tz)


def next_payday(day: int, time_str: str, tz_name: str, after: datetime | None = None) -> datetime:
    """Next payday strictly after ``after`` (UTC). Days past month end use the last day."""
    tz = get_tz(tz_name)
    hh, mm = parse_hhmm(time_str)
    after = (after or utcnow()).astimezone(tz)
    year, month = after.year, after.month
    for _ in range(3):
        candidate = _payday_in_month(year, month, day, hh, mm, tz)
        if candidate > after:
            return candidate.astimezone(timezone.utc)
        month += 1
        if month > 12:
            month, year = 1, year + 1
    raise RuntimeError("Could not compute next payday")  # pragma: no cover


def period_for(moment: datetime, tz_name: str) -> tuple[str, str]:
    """('2026-10', 'October 2026') for the local month containing ``moment``."""
    local = moment.astimezone(get_tz(tz_name))
    return local.strftime("%Y-%m"), local.strftime("%B %Y")


def add_months(moment: datetime, months: int) -> datetime:
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def days_until(moment: datetime, now: datetime | None = None) -> float:
    return (moment - (now or utcnow())) / timedelta(days=1)
