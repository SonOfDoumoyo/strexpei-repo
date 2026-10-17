"""Runtime platform settings (editable by admins) with safe defaults."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.money import FeeSchedule
from ..models import PlatformSetting

DEFAULTS: dict[str, Any] = {
    "fees": FeeSchedule().to_dict(),
    "trial_days": 14,
    "trial_ai_quota": 30,
    "annual_discount_months": 2,  # annual billing = 10 months price
    "grace_days": 3,
    "max_seats_per_workgroup": 5000,
    "payday_reminder_days": 3,
}


async def get_setting(session: AsyncSession, key: str) -> Any:
    row = await session.get(PlatformSetting, key)
    if row is None or row.value is None:
        return DEFAULTS.get(key)
    return row.value


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.get(PlatformSetting, key)
    if row is None:
        session.add(PlatformSetting(key=key, value=value))
    else:
        row.value = value


async def all_settings(session: AsyncSession) -> dict[str, Any]:
    result = dict(DEFAULTS)
    rows = (await session.execute(select(PlatformSetting))).scalars().all()
    for row in rows:
        result[row.key] = row.value
    result["fees"] = FeeSchedule.from_dict(result.get("fees")).to_dict()
    return result


async def get_fees(session: AsyncSession) -> FeeSchedule:
    return FeeSchedule.from_dict(await get_setting(session, "fees"))


async def get_int(session: AsyncSession, key: str) -> int:
    value = await get_setting(session, key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(DEFAULTS[key])
