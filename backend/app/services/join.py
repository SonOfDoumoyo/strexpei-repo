"""Public staff onboarding: no account needed.

The staff member opens the workgroup's link (or scans its QR code), enters
the staff ID they were given, then their personal and bank details. The ID
must exist in that workgroup and be unclaimed; the bank account is verified
with Paystack before anything is saved.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import AppError, Conflict, NotFound
from ..core.ids import normalise_staff_code
from ..core.redis import hit_rate_limit
from ..core.timeutil import utcnow
from ..models import StaffMember, Workgroup
from . import billing
from .activity import audit, notify
from .mailer import mask_account, queue_email
from .staff import attach_bank, verify_bank_account


class StaffIdNotFound(AppError):
    status_code = 404
    code = "staff_id_not_found"


class StaffIdTaken(Conflict):
    code = "staff_id_taken"


async def get_workgroup_by_code(session: AsyncSession, invite_code: str) -> Workgroup:
    workgroup = (
        await session.execute(select(Workgroup).where(Workgroup.invite_code == invite_code.strip().lower()))
    ).unique().scalar_one_or_none()
    if workgroup is None or workgroup.status != "active":
        raise NotFound("This onboarding link is invalid or has been replaced. Ask your finance team for the current link.", code="invite_invalid")
    return workgroup


async def accepting_reason(session: AsyncSession, workgroup: Workgroup) -> str | None:
    if not workgroup.invite_active:
        return "Registration is paused for this workgroup. Please check back later or contact your finance team."
    if not await billing.is_usable(session, workgroup.subscription):
        return "Registration is temporarily unavailable for this workgroup. Please contact your finance team."
    return None


async def public_info(session: AsyncSession, invite_code: str) -> dict[str, Any]:
    workgroup = await get_workgroup_by_code(session, invite_code)
    reason = await accepting_reason(session, workgroup)
    owner = workgroup.owner
    return {
        "workgroup": {"name": workgroup.name, "address": workgroup.address, "industry": workgroup.industry},
        "manager_name": owner.full_name if owner else None,
        "accepting": reason is None,
        "message": reason,
        "staff_id_hint": f"{workgroup.staff_id_prefix}-XXXX-XXXX",
    }


async def _ensure_accepting(session: AsyncSession, workgroup: Workgroup) -> None:
    reason = await accepting_reason(session, workgroup)
    if reason:
        raise AppError(reason, code="registration_closed", status_code=403)


async def _find_pending(session: AsyncSession, workgroup: Workgroup, staff_code: str, *, lock: bool = False) -> StaffMember:
    norm = normalise_staff_code(staff_code or "")
    if not norm:
        raise StaffIdNotFound("Enter your staff ID.")
    stmt = select(StaffMember).where(StaffMember.workgroup_id == workgroup.id, StaffMember.staff_code_norm == norm)
    if lock:
        stmt = stmt.with_for_update(of=StaffMember)
    member = (await session.execute(stmt)).unique().scalar_one_or_none()
    if member is None or member.status == "inactive":
        raise StaffIdNotFound(
            f"We couldn't find staff ID “{staff_code.strip()}” for {workgroup.name}. Check it carefully or ask your finance team."
        )
    if member.status == "registered":
        raise StaffIdTaken(
            f"Staff ID “{member.staff_code}” has already been registered. If that wasn't you, contact your finance team right away."
        )
    return member


async def check_staff_id(session: AsyncSession, invite_code: str, staff_code: str, ip: str) -> dict[str, Any]:
    workgroup = await get_workgroup_by_code(session, invite_code)
    await _ensure_accepting(session, workgroup)
    await hit_rate_limit("join-check-ip", ip, 30, 600)
    await hit_rate_limit("join-check-wg", str(workgroup.id), 600, 600)
    member = await _find_pending(session, workgroup, staff_code)
    first, last = None, None
    if member.preset_name:
        parts = member.preset_name.split()
        first, last = parts[0], " ".join(parts[1:]) or None
    return {
        "staff_code": member.staff_code,
        "preset": {"first_name": first, "last_name": last, "email": member.email, "phone": member.phone,
                   "role": member.role.name if member.role else None},
    }


async def resolve_account(session: AsyncSession, invite_code: str, staff_code: str, account_number: str, bank_code: str, ip: str) -> dict[str, Any]:
    workgroup = await get_workgroup_by_code(session, invite_code)
    await _ensure_accepting(session, workgroup)
    await hit_rate_limit("join-resolve-ip", ip, 20, 600)
    await _find_pending(session, workgroup, staff_code)
    account_name, bank = await verify_bank_account(account_number, bank_code)
    return {"account_name": account_name, "bank_name": bank}


async def register(session: AsyncSession, invite_code: str, data: dict[str, Any], ip: str) -> dict[str, Any]:
    workgroup = await get_workgroup_by_code(session, invite_code)
    await _ensure_accepting(session, workgroup)
    await hit_rate_limit("join-register-ip", ip, 10, 600)
    member = await _find_pending(session, workgroup, data["staff_code"], lock=True)

    member.first_name = data["first_name"].strip()
    member.last_name = data["last_name"].strip()
    member.email = data["email"].strip().lower()
    member.phone = (data.get("phone") or "").strip() or None
    await attach_bank(session, member, data["account_number"], data["bank_code"])
    member.status = "registered"
    member.registered_at = utcnow()
    member.registration_ip = ip

    audit(
        session,
        action="staff.registered",
        summary=f"{member.display_name} registered with staff ID {member.staff_code}",
        actor_label=member.display_name,
        workgroup_id=workgroup.id,
        meta={"staff_id": str(member.id), "name_match": member.name_match},
        ip=ip,
    )
    owner = workgroup.owner
    warn = "" if member.name_match else " The bank account name doesn't match the name entered — please review."
    notify(
        session,
        owner.id,
        f"{member.display_name} joined {workgroup.name}",
        f"Staff ID {member.staff_code} registered. Bank: {member.bank_name} {mask_account(member.account_number)} ({member.account_name}).{warn}",
        kind="success" if member.name_match else "warning",
        link=f"/app/staff?focus={member.id}",
        workgroup_id=workgroup.id,
    )
    queue_email(
        session,
        member.email,
        "staff_welcome",
        {
            "staff_name": member.first_name,
            "company": workgroup.name,
            "staff_code": member.staff_code,
            "account_name": member.account_name,
            "bank_name": member.bank_name,
            "account_masked": mask_account(member.account_number),
        },
    )
    await session.flush()
    remaining = (
        await session.execute(
            select(func.count()).select_from(StaffMember).where(StaffMember.workgroup_id == workgroup.id, StaffMember.status == "pending")
        )
    ).scalar_one()
    registered = (
        await session.execute(
            select(func.count()).select_from(StaffMember).where(StaffMember.workgroup_id == workgroup.id, StaffMember.status == "registered")
        )
    ).scalar_one()
    if remaining == 0 and registered >= workgroup.headcount:
        queue_email(
            session,
            owner.email,
            "all_staff_registered",
            {"name": owner.first_name, "company": workgroup.name, "count": registered, "link": f"{settings.FRONTEND_URL}/app/staff"},
        )
    return {
        "staff_code": member.staff_code,
        "name": member.display_name,
        "workgroup": workgroup.name,
        "bank_name": member.bank_name,
        "account_masked": mask_account(member.account_number),
        "account_name": member.account_name,
    }
