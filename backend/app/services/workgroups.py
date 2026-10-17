"""Workgroups: a business (or branch) whose staff are paid together."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import NotFound, ValidationFailed
from ..core.ids import generate_invite_code, prefix_from_name
from ..core.money import PayoutBreakdown
from ..core.timeutil import next_payday, parse_hhmm
from ..models import AuditLog, PayrollRun, StaffMember, User, Workgroup
from . import billing, platform
from .activity import audit

PAYMENT_MODES = {"manual", "automatic"}


def join_url(workgroup: Workgroup) -> str:
    return f"{settings.FRONTEND_URL}/join/{workgroup.invite_code}"


async def create_workgroup(
    session: AsyncSession,
    owner: User,
    *,
    name: str,
    address: str | None,
    industry: str | None,
    headcount: int,
    payment_mode: str = "manual",
    payday_day: int = 25,
    payday_time: str = "09:00",
) -> Workgroup:
    max_seats = await platform.get_int(session, "max_seats_per_workgroup")
    if headcount < 1 or headcount > max_seats:
        raise ValidationFailed(f"Number of staff must be between 1 and {max_seats}.")
    _validate_schedule(payment_mode, payday_day, payday_time)
    workgroup = Workgroup(
        owner_id=owner.id,
        name=name.strip(),
        address=(address or "").strip() or None,
        industry=(industry or "").strip() or None,
        headcount=headcount,
        staff_id_prefix=prefix_from_name(name),
        invite_code=generate_invite_code(),
        payment_mode=payment_mode,
        payday_day=payday_day,
        payday_time=payday_time,
        timezone=settings.TIMEZONE,
    )
    workgroup.next_payday_at = next_payday(payday_day, payday_time, workgroup.timezone)
    session.add(workgroup)
    await session.flush()
    workgroup.owner = owner
    await billing.create_trial(session, workgroup)
    audit(session, action="workgroup.created", summary=f"Created workgroup {workgroup.name} for {headcount} staff", actor=owner, workgroup_id=workgroup.id)
    return workgroup


def _validate_schedule(payment_mode: str, payday_day: int, payday_time: str) -> None:
    if payment_mode not in PAYMENT_MODES:
        raise ValidationFailed("Payment mode must be manual or automatic.")
    if not 1 <= payday_day <= 31:
        raise ValidationFailed("Payday must be a day between 1 and 31.")
    try:
        parse_hhmm(payday_time)
    except (ValueError, AttributeError):
        raise ValidationFailed("Payday time must look like 09:00.")


async def list_for_user(session: AsyncSession, user: User) -> list[Workgroup]:
    return list(
        (
            await session.execute(
                select(Workgroup).where(Workgroup.owner_id == user.id, Workgroup.status == "active").order_by(Workgroup.created_at)
            )
        )
        .unique()
        .scalars()
        .all()
    )


async def get_owned(session: AsyncSession, user: User, workgroup_id: uuid.UUID) -> Workgroup:
    workgroup = await session.get(Workgroup, workgroup_id)
    if workgroup is None or workgroup.owner_id != user.id or workgroup.status != "active":
        raise NotFound("Workgroup not found.")
    return workgroup


async def update_workgroup(session: AsyncSession, workgroup: Workgroup, actor: User, data: dict[str, Any]) -> Workgroup:
    changes: list[str] = []
    if "name" in data and data["name"]:
        workgroup.name = data["name"].strip()
        changes.append("name")
    for field in ("address", "industry"):
        if field in data:
            setattr(workgroup, field, (data[field] or "").strip() or None)
            changes.append(field)
    mode = data.get("payment_mode", workgroup.payment_mode)
    day = data.get("payday_day", workgroup.payday_day)
    time = data.get("payday_time", workgroup.payday_time)
    if any(key in data for key in ("payment_mode", "payday_day", "payday_time")):
        _validate_schedule(mode, day, time)
        workgroup.payment_mode = mode
        workgroup.payday_day = day
        workgroup.payday_time = time
        workgroup.next_payday_at = next_payday(day, time, workgroup.timezone)
        workgroup.last_reminder_key = None
        changes.append("payroll schedule")
    if "auto_renew" in data and workgroup.subscription is not None:
        workgroup.subscription.auto_renew = bool(data["auto_renew"])
        changes.append("auto-renew")
    if changes:
        audit(session, action="workgroup.updated", summary=f"Updated {', '.join(changes)}", actor=actor, workgroup_id=workgroup.id, meta=data)
    return workgroup


async def rotate_invite(session: AsyncSession, workgroup: Workgroup, actor: User) -> Workgroup:
    from ..core.timeutil import utcnow

    for _ in range(5):
        workgroup.invite_code = generate_invite_code()
        try:
            async with session.begin_nested():
                await session.flush()
            break
        except IntegrityError:
            continue
    workgroup.invite_rotated_at = utcnow()
    workgroup.invite_active = True
    audit(session, action="invite.rotated", summary="Generated a new onboarding link (old link disabled)", actor=actor, workgroup_id=workgroup.id)
    return workgroup


async def set_invite_active(session: AsyncSession, workgroup: Workgroup, actor: User, active: bool) -> Workgroup:
    workgroup.invite_active = active
    audit(
        session,
        action="invite.toggled",
        summary="Opened the onboarding link" if active else "Paused the onboarding link",
        actor=actor,
        workgroup_id=workgroup.id,
    )
    return workgroup


async def staff_stats(session: AsyncSession, workgroup_id: uuid.UUID) -> dict[str, int]:
    rows = (
        await session.execute(
            select(StaffMember.status, func.count()).where(StaffMember.workgroup_id == workgroup_id).group_by(StaffMember.status)
        )
    ).all()
    counts = {status: count for status, count in rows}
    staff = (
        (
            await session.execute(
                select(StaffMember).where(StaffMember.workgroup_id == workgroup_id, StaffMember.status == "registered")
            )
        )
        .unique()
        .scalars()
        .all()
    )
    ready = sum(1 for s in staff if s.payout_ready)
    missing_salary = sum(1 for s in staff if s.effective_salary_kobo <= 0)
    mismatched = sum(1 for s in staff if s.name_match is False)
    payroll = sum(s.effective_salary_kobo for s in staff if s.payout_ready)
    return {
        "total": sum(counts.values()),
        "registered": counts.get("registered", 0),
        "pending": counts.get("pending", 0),
        "inactive": counts.get("inactive", 0),
        "payout_ready": ready,
        "missing_salary": missing_salary,
        "name_mismatch": mismatched,
        "monthly_payroll_kobo": payroll,
    }


async def estimate_payroll(session: AsyncSession, workgroup_id: uuid.UUID) -> dict[str, int]:
    fees = await platform.get_fees(session)
    staff = (
        (await session.execute(select(StaffMember).where(StaffMember.workgroup_id == workgroup_id, StaffMember.status == "registered")))
        .unique()
        .scalars()
        .all()
    )
    breakdown = PayoutBreakdown()
    for member in staff:
        if member.payout_ready:
            breakdown.add(member.effective_salary_kobo, fees)
    return breakdown.as_dict()


async def overview(session: AsyncSession, workgroup: Workgroup) -> dict[str, Any]:
    stats = await staff_stats(session, workgroup.id)
    estimate = await estimate_payroll(session, workgroup.id)
    last_run = (
        await session.execute(
            select(PayrollRun).where(PayrollRun.workgroup_id == workgroup.id).order_by(PayrollRun.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    completed_runs = (
        await session.execute(
            select(func.count()).select_from(PayrollRun).where(
                PayrollRun.workgroup_id == workgroup.id, PayrollRun.status.in_(["completed", "partially_failed"])
            )
        )
    ).scalar_one()
    activity = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.workgroup_id == workgroup.id).order_by(AuditLog.created_at.desc()).limit(6)
            )
        )
        .scalars()
        .all()
    )
    sub = await billing.subscription_out(session, workgroup.subscription)
    checklist = [
        {"key": "ids", "label": "Create staff IDs", "done": stats["total"] > 0, "link": "/app/staff-ids"},
        {"key": "share", "label": "Share the onboarding link", "done": stats["registered"] > 0, "link": "/app/onboarding"},
        {"key": "salaries", "label": "Set salaries", "done": stats["registered"] > 0 and stats["missing_salary"] == 0, "link": "/app/staff"},
        {"key": "fund", "label": "Fund the wallet", "done": workgroup.wallet_balance_kobo > 0 and workgroup.wallet_balance_kobo >= estimate["total_kobo"], "link": "/app/wallet"},
        {"key": "pay", "label": "Run your first payroll", "done": completed_runs > 0, "link": "/app/payroll"},
    ]
    return {
        "workgroup": workgroup_out(workgroup),
        "staff": stats,
        "estimate": estimate,
        "wallet_balance_kobo": workgroup.wallet_balance_kobo,
        "shortfall_kobo": max(0, estimate["total_kobo"] - workgroup.wallet_balance_kobo),
        "subscription": sub,
        "last_run": run_summary(last_run) if last_run else None,
        "checklist": checklist,
        "activity": [audit_out(a) for a in activity],
    }


def workgroup_out(workgroup: Workgroup) -> dict[str, Any]:
    return {
        "id": str(workgroup.id),
        "name": workgroup.name,
        "address": workgroup.address,
        "industry": workgroup.industry,
        "headcount": workgroup.headcount,
        "staff_id_prefix": workgroup.staff_id_prefix,
        "invite_code": workgroup.invite_code,
        "invite_active": workgroup.invite_active,
        "join_url": join_url(workgroup),
        "payment_mode": workgroup.payment_mode,
        "payday_day": workgroup.payday_day,
        "payday_time": workgroup.payday_time,
        "timezone": workgroup.timezone,
        "next_payday_at": workgroup.next_payday_at,
        "wallet_balance_kobo": workgroup.wallet_balance_kobo,
        "dva": (
            {"account_number": workgroup.dva_account_number, "account_name": workgroup.dva_account_name, "bank_name": workgroup.dva_bank_name}
            if workgroup.dva_account_number
            else None
        ),
        "subscription_status": workgroup.subscription.status if workgroup.subscription else None,
        "created_at": workgroup.created_at,
    }


def run_summary(run: PayrollRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "number": run.number,
        "status": run.status,
        "trigger": run.trigger,
        "period_label": run.period_label,
        "staff_count": run.staff_count,
        "total_kobo": run.total_kobo,
        "salaries_kobo": run.salaries_kobo,
        "paid_kobo": run.paid_kobo,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


def audit_out(log: AuditLog) -> dict[str, Any]:
    return {
        "id": str(log.id),
        "action": log.action,
        "summary": log.summary,
        "actor": log.actor_label,
        "created_at": log.created_at,
        "meta": log.meta,
    }
