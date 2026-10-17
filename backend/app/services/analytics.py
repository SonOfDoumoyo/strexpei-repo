from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutil import add_months, get_tz, utcnow
from ..models import PayrollItem, StaffMember, WalletEntry, Workgroup


def _month_keys(months: int, tz_name: str) -> list[str]:
    now = utcnow().astimezone(get_tz(tz_name)).replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    return [add_months(now, -offset).strftime("%Y-%m") for offset in range(months - 1, -1, -1)]


async def workgroup_analytics(session: AsyncSession, workgroup: Workgroup, months: int = 12) -> dict[str, Any]:
    months = max(3, min(24, months))
    tz = workgroup.timezone
    keys = _month_keys(months, tz)
    since = utcnow() - timedelta(days=months * 31 + 5)
    month_expr = func.to_char(func.timezone(tz, PayrollItem.paid_at), "YYYY-MM")
    rows = (
        await session.execute(
            select(month_expr, func.sum(PayrollItem.amount_kobo), func.sum(PayrollItem.fee_kobo), func.sum(PayrollItem.commission_kobo),
                   func.count(func.distinct(PayrollItem.staff_id)))
            .where(PayrollItem.workgroup_id == workgroup.id, PayrollItem.status == "success", PayrollItem.paid_at >= since)
            .group_by(month_expr)
        )
    ).all()
    by_month = {r[0]: r for r in rows}
    series = []
    for key in keys:
        row = by_month.get(key)
        series.append({
            "month": key,
            "salaries_kobo": int(row[1] or 0) if row else 0,
            "fees_kobo": int((row[2] or 0) + (row[3] or 0)) if row else 0,
            "staff_paid": int(row[4] or 0) if row else 0,
        })

    lifetime = (
        await session.execute(
            select(func.coalesce(func.sum(PayrollItem.amount_kobo), 0), func.coalesce(func.sum(PayrollItem.fee_kobo + PayrollItem.commission_kobo), 0),
                   func.count())
            .where(PayrollItem.workgroup_id == workgroup.id, PayrollItem.status == "success")
        )
    ).one()
    failed = (
        await session.execute(
            select(func.count()).select_from(PayrollItem).where(PayrollItem.workgroup_id == workgroup.id, PayrollItem.status.in_(["failed", "reversed"]))
        )
    ).scalar_one()
    funded = (
        await session.execute(
            select(func.coalesce(func.sum(WalletEntry.amount_kobo), 0)).where(WalletEntry.workgroup_id == workgroup.id, WalletEntry.entry_type == "funding")
        )
    ).scalar_one()

    staff = (
        (await session.execute(select(StaffMember).where(StaffMember.workgroup_id == workgroup.id, StaffMember.status == "registered")))
        .unique().scalars().all()
    )
    by_role: dict[str, dict[str, int]] = defaultdict(lambda: {"staff": 0, "salaries_kobo": 0})
    salaries = []
    for member in staff:
        label = member.role.name if member.role else "No role"
        by_role[label]["staff"] += 1
        by_role[label]["salaries_kobo"] += member.effective_salary_kobo
        if member.effective_salary_kobo > 0:
            salaries.append(member.effective_salary_kobo)
    salaries.sort()
    median = salaries[len(salaries) // 2] if salaries else 0

    reg_month = func.to_char(func.timezone(tz, StaffMember.registered_at), "YYYY-MM")
    reg_rows = dict(
        (
            await session.execute(
                select(reg_month, func.count()).where(StaffMember.workgroup_id == workgroup.id, StaffMember.registered_at.is_not(None)).group_by(reg_month)
            )
        ).all()
    )
    before = (
        await session.execute(
            select(func.count()).select_from(StaffMember).where(
                StaffMember.workgroup_id == workgroup.id, StaffMember.registered_at.is_not(None), reg_month < keys[0]
            )
        )
    ).scalar_one()
    running = int(before)
    headcount = []
    for key in keys:
        running += int(reg_rows.get(key, 0))
        headcount.append({"month": key, "registered": running})

    last, prev = series[-1]["salaries_kobo"], series[-2]["salaries_kobo"] if len(series) > 1 else 0
    return {
        "series": series,
        "headcount": headcount,
        "by_role": sorted(({"role": k, **v} for k, v in by_role.items()), key=lambda r: -r["salaries_kobo"]),
        "totals": {
            "lifetime_paid_kobo": int(lifetime[0]),
            "lifetime_fees_kobo": int(lifetime[1]),
            "payments_count": int(lifetime[2]),
            "failed_count": int(failed),
            "success_rate": round(lifetime[2] / (lifetime[2] + failed) * 100, 1) if (lifetime[2] + failed) else None,
            "funded_kobo": int(funded),
            "monthly_payroll_kobo": sum(salaries),
            "median_salary_kobo": median,
            "average_salary_kobo": round(sum(salaries) / len(salaries)) if salaries else 0,
            "month_change_pct": round((last - prev) / prev * 100, 1) if prev else None,
        },
    }


async def staff_payment_history(session: AsyncSession, workgroup_id: uuid.UUID, staff_id: uuid.UUID) -> list[dict[str, Any]]:
    from ..models import PayrollRun

    rows = (
        await session.execute(
            select(PayrollItem, PayrollRun.number, PayrollRun.period_label)
            .join(PayrollRun, PayrollRun.id == PayrollItem.run_id)
            .where(PayrollItem.workgroup_id == workgroup_id, PayrollItem.staff_id == staff_id, PayrollItem.status != "pending")
            .order_by(PayrollItem.created_at.desc())
            .limit(36)
        )
    ).all()
    return [
        {"id": str(i.id), "run_id": str(i.run_id), "run_number": number, "period": period, "amount_kobo": i.amount_kobo, "status": i.status,
         "paid_at": i.paid_at, "reference": i.reference, "failure_reason": i.failure_reason, "bank_name": i.bank_name,
         "account_number_masked": "••••" + i.account_number[-4:]}
        for i, number, period in rows
    ]
