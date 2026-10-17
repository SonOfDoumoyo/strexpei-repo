"""Platform owner console: revenue, users, workgroups, pricing."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutil import add_months, get_tz, utcnow
from ..core.config import settings
from ..models import Invoice, PayrollItem, PayrollRun, StaffMember, Subscription, User, WalletEntry, Workgroup
from . import billing
from .paystack import PaystackError, get_provider


async def overview(session: AsyncSession) -> dict[str, Any]:
    now = utcnow()
    tz = settings.TIMEZONE
    month_start_local = now.astimezone(get_tz(tz)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    commission_total = (
        await session.execute(select(func.coalesce(func.sum(PayrollItem.commission_kobo), 0)).where(PayrollItem.status == "success"))
    ).scalar_one()
    disbursed_total = (
        await session.execute(select(func.coalesce(func.sum(PayrollItem.amount_kobo), 0)).where(PayrollItem.status == "success"))
    ).scalar_one()
    subscription_total = (
        await session.execute(select(func.coalesce(func.sum(Invoice.amount_kobo), 0)).where(Invoice.status == "paid"))
    ).scalar_one()
    commission_month = (
        await session.execute(
            select(func.coalesce(func.sum(PayrollItem.commission_kobo), 0)).where(PayrollItem.status == "success", PayrollItem.paid_at >= month_start_local)
        )
    ).scalar_one()
    subscription_month = (
        await session.execute(
            select(func.coalesce(func.sum(Invoice.amount_kobo), 0)).where(Invoice.status == "paid", Invoice.paid_at >= month_start_local)
        )
    ).scalar_one()
    held = (await session.execute(select(func.coalesce(func.sum(Workgroup.wallet_balance_kobo), 0)))).scalar_one()

    subs = (await session.execute(select(Subscription))).scalars().all()
    mrr = 0
    status_counts: dict[str, int] = {}
    plan_counts: dict[str, int] = {}
    for sub in subs:
        status_counts[sub.status] = status_counts.get(sub.status, 0) + 1
        if sub.status in ("active", "past_due"):
            plan = sub.plan
            mrr += billing.monthly_price(plan, sub.seats)
            plan_counts[plan.name] = plan_counts.get(plan.name, 0) + 1

    users = (await session.execute(select(func.count()).select_from(User).where(User.role == "manager", User.status != "purged"))).scalar_one()
    workgroups = (await session.execute(select(func.count()).select_from(Workgroup).where(Workgroup.status == "active"))).scalar_one()
    staff = (await session.execute(select(func.count()).select_from(StaffMember).where(StaffMember.status == "registered"))).scalar_one()
    runs_month = (
        await session.execute(select(func.count()).select_from(PayrollRun).where(PayrollRun.created_at >= month_start_local))
    ).scalar_one()

    keys = [add_months(month_start_local, -o).strftime("%Y-%m") for o in range(11, -1, -1)]
    since = add_months(month_start_local, -11)
    c_month = func.to_char(func.timezone(tz, PayrollItem.paid_at), "YYYY-MM")
    commission_rows = dict(
        (await session.execute(select(c_month, func.sum(PayrollItem.commission_kobo)).where(
            PayrollItem.status == "success", PayrollItem.paid_at >= since).group_by(c_month))).all()
    )
    disbursed_rows = dict(
        (await session.execute(select(c_month, func.sum(PayrollItem.amount_kobo)).where(
            PayrollItem.status == "success", PayrollItem.paid_at >= since).group_by(c_month))).all()
    )
    i_month = func.to_char(func.timezone(tz, Invoice.paid_at), "YYYY-MM")
    sub_rows = dict(
        (await session.execute(select(i_month, func.sum(Invoice.amount_kobo)).where(Invoice.status == "paid", Invoice.paid_at >= since).group_by(i_month))).all()
    )
    series = [
        {"month": k, "commission_kobo": int(commission_rows.get(k) or 0), "subscriptions_kobo": int(sub_rows.get(k) or 0),
         "disbursed_kobo": int(disbursed_rows.get(k) or 0)}
        for k in keys
    ]

    paystack_balance = None
    try:
        paystack_balance = await get_provider().get_balance()
    except (PaystackError, Exception):
        paystack_balance = None

    return {
        "revenue": {
            "total_kobo": int(commission_total) + int(subscription_total),
            "commission_kobo": int(commission_total),
            "subscriptions_kobo": int(subscription_total),
            "this_month_kobo": int(commission_month) + int(subscription_month),
            "commission_month_kobo": int(commission_month),
            "subscriptions_month_kobo": int(subscription_month),
            "mrr_kobo": mrr,
        },
        "volume": {"disbursed_kobo": int(disbursed_total), "wallets_held_kobo": int(held), "paystack_balance_kobo": paystack_balance},
        "counts": {"managers": users, "workgroups": workgroups, "staff": staff, "payroll_runs_this_month": runs_month},
        "subscriptions": {"by_status": status_counts, "by_plan": plan_counts},
        "series": series,
    }


async def list_users(session: AsyncSession, q: str | None, status: str | None, page: int, page_size: int) -> dict[str, Any]:
    stmt = select(User).where(User.status != "purged")
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.first_name + " " + User.last_name).like(like)))
    if status:
        stmt = stmt.where(User.status == status)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    users = (await session.execute(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    counts = dict(
        (await session.execute(select(Workgroup.owner_id, func.count()).where(Workgroup.owner_id.in_([u.id for u in users])).group_by(Workgroup.owner_id))).all()
    ) if users else {}
    return {
        "items": [
            {"id": str(u.id), "email": u.email, "name": u.full_name, "phone": u.phone, "role": u.role, "status": u.status,
             "verified": u.is_verified, "workgroups": counts.get(u.id, 0), "created_at": u.created_at, "last_login_at": u.last_login_at}
            for u in users
        ],
        "total": total, "page": page, "page_size": page_size,
    }


async def list_workgroups(session: AsyncSession, q: str | None, page: int, page_size: int) -> dict[str, Any]:
    stmt = select(Workgroup)
    if q:
        stmt = stmt.where(func.lower(Workgroup.name).like(f"%{q.lower()}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Workgroup.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).unique().scalars().all()
    ids = [w.id for w in rows]
    staff_counts = dict(
        (await session.execute(select(StaffMember.workgroup_id, func.count()).where(StaffMember.workgroup_id.in_(ids), StaffMember.status == "registered")
                               .group_by(StaffMember.workgroup_id))).all()
    ) if ids else {}
    paid = dict(
        (await session.execute(select(PayrollItem.workgroup_id, func.sum(PayrollItem.amount_kobo)).where(PayrollItem.workgroup_id.in_(ids),
                               PayrollItem.status == "success").group_by(PayrollItem.workgroup_id))).all()
    ) if ids else {}
    commission = dict(
        (await session.execute(select(PayrollItem.workgroup_id, func.sum(PayrollItem.commission_kobo)).where(PayrollItem.workgroup_id.in_(ids),
                               PayrollItem.status == "success").group_by(PayrollItem.workgroup_id))).all()
    ) if ids else {}
    items = []
    for w in rows:
        sub = w.subscription
        items.append({
            "id": str(w.id), "name": w.name, "owner": w.owner.full_name if w.owner else None, "owner_email": w.owner.email if w.owner else None,
            "status": w.status, "headcount": w.headcount, "registered_staff": staff_counts.get(w.id, 0), "wallet_balance_kobo": w.wallet_balance_kobo,
            "payment_mode": w.payment_mode, "plan": sub.plan.name if sub else None, "subscription_status": sub.status if sub else None,
            "disbursed_kobo": int(paid.get(w.id) or 0), "commission_kobo": int(commission.get(w.id) or 0), "created_at": w.created_at,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def list_runs(session: AsyncSession, status: str | None, page: int, page_size: int) -> dict[str, Any]:
    stmt = select(PayrollRun, Workgroup.name).join(Workgroup, Workgroup.id == PayrollRun.workgroup_id)
    if status:
        stmt = stmt.where(PayrollRun.status == status)
    total = (await session.execute(select(func.count()).select_from(PayrollRun).where(PayrollRun.status == status) if status else select(func.count()).select_from(PayrollRun))).scalar_one()
    rows = (await session.execute(stmt.order_by(PayrollRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return {
        "items": [
            {"id": str(r.id), "number": r.number, "workgroup": name, "status": r.status, "trigger": r.trigger, "staff_count": r.staff_count,
             "salaries_kobo": r.salaries_kobo, "commission_kobo": r.commission_kobo, "total_kobo": r.total_kobo, "paid_kobo": r.paid_kobo,
             "created_at": r.created_at, "completed_at": r.completed_at}
            for r, name in rows
        ],
        "total": total, "page": page, "page_size": page_size,
    }


async def revenue_ledger(session: AsyncSession, days: int = 90) -> list[list[Any]]:
    since = utcnow() - timedelta(days=days)
    rows: list[list[Any]] = []
    items = (
        await session.execute(
            select(PayrollItem, Workgroup.name).join(Workgroup, Workgroup.id == PayrollItem.workgroup_id)
            .where(PayrollItem.status == "success", PayrollItem.paid_at >= since).order_by(PayrollItem.paid_at)
        )
    ).all()
    for item, name in items:
        rows.append([item.paid_at.strftime("%Y-%m-%d %H:%M"), "commission", name, item.reference, f"{item.commission_kobo / 100:.2f}",
                     f"{item.amount_kobo / 100:.2f}"])
    invoices = (
        await session.execute(
            select(Invoice, Workgroup.name).join(Workgroup, Workgroup.id == Invoice.workgroup_id)
            .where(Invoice.status == "paid", Invoice.paid_at >= since).order_by(Invoice.paid_at)
        )
    ).all()
    for invoice, name in invoices:
        rows.append([invoice.paid_at.strftime("%Y-%m-%d %H:%M"), f"subscription ({invoice.kind})", name, invoice.number,
                     f"{invoice.amount_kobo / 100:.2f}", ""])
    rows.sort(key=lambda r: r[0])
    return rows


async def ledger_integrity(session: AsyncSession) -> dict[str, Any]:
    """Wallet balances must equal the sum of their ledger entries."""
    credit = func.coalesce(func.sum(case((WalletEntry.direction == "credit", WalletEntry.amount_kobo), else_=0)), 0)
    debit = func.coalesce(func.sum(case((WalletEntry.direction == "debit", WalletEntry.amount_kobo), else_=0)), 0)
    rows = (await session.execute(select(WalletEntry.workgroup_id, credit - debit).group_by(WalletEntry.workgroup_id))).all()
    ledger = {wid: int(total) for wid, total in rows}
    mismatches = []
    for workgroup in (await session.execute(select(Workgroup))).unique().scalars().all():
        expected = ledger.get(workgroup.id, 0)
        if expected != workgroup.wallet_balance_kobo:
            mismatches.append({"workgroup_id": str(workgroup.id), "name": workgroup.name, "balance_kobo": workgroup.wallet_balance_kobo,
                               "ledger_kobo": expected})
    return {"ok": not mismatches, "mismatches": mismatches}
