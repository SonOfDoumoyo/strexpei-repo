from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from ...core.errors import Conflict, Unauthorized
from ...core.redis import hit_rate_limit
from ...core.security import verify_password
from ...models import AuditLog, PayrollRun
from ...schemas.requests import InviteEmailIn, InviteToggleIn, PasswordIn, WorkgroupCreateIn, WorkgroupUpdateIn
from ...services import analytics, billing
from ...services import workgroups as service
from ...services.activity import audit
from ...services.mailer import queue_email
from ..deps import Manager, OwnedWorkgroup, SessionDep

router = APIRouter(prefix="/workgroups", tags=["workgroups"])


async def _with_subscription(session, workgroup) -> dict[str, Any]:
    data = service.workgroup_out(workgroup)
    data["subscription"] = await billing.subscription_out(session, workgroup.subscription)
    data["seats_in_use"] = await billing.seats_in_use(session, workgroup.id)
    return data


@router.get("")
async def list_workgroups(user: Manager, session: SessionDep) -> list[dict[str, Any]]:
    items = await service.list_for_user(session, user)
    return [await _with_subscription(session, w) for w in items]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workgroup(body: WorkgroupCreateIn, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("create-workgroup", str(user.id), 20, 3600)
    workgroup = await service.create_workgroup(session, user, **body.model_dump())
    await session.commit()
    workgroup = await service.get_owned(session, user, workgroup.id)
    return await _with_subscription(session, workgroup)


@router.get("/{workgroup_id}")
async def get_workgroup(workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    return await _with_subscription(session, workgroup)


@router.patch("/{workgroup_id}")
async def update_workgroup(body: WorkgroupUpdateIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    await service.update_workgroup(session, workgroup, user, body.model_dump(exclude_unset=True))
    await session.commit()
    return await _with_subscription(session, workgroup)


@router.post("/{workgroup_id}/archive")
async def archive_workgroup(body: PasswordIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, str]:
    if not await verify_password(body.password, user.password_hash):
        raise Unauthorized("Incorrect password.", code="invalid_password")
    if workgroup.wallet_balance_kobo > 0:
        raise Conflict("Withdraw the wallet balance before deleting this workgroup. Open Wallet and choose Withdraw.", code="wallet_not_empty")
    from ...services.withdrawals import in_flight

    if await in_flight(session, [workgroup.id]):
        raise Conflict("Wait for the withdrawal in progress to finish first.")
    active = (
        await session.execute(
            select(func.count()).select_from(PayrollRun).where(PayrollRun.workgroup_id == workgroup.id, PayrollRun.status == "processing")
        )
    ).scalar_one()
    if active:
        raise Conflict("Wait for the payroll in progress to finish first.")
    workgroup.status = "archived"
    workgroup.invite_active = False
    if workgroup.subscription:
        workgroup.subscription.auto_renew = False
    audit(session, action="workgroup.archived", summary=f"Deleted workgroup {workgroup.name}", actor=user, workgroup_id=workgroup.id)
    await session.commit()
    return {"message": f"{workgroup.name} has been deleted."}


@router.get("/{workgroup_id}/overview")
async def overview(workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    return await service.overview(session, workgroup)


@router.post("/{workgroup_id}/invite/rotate")
async def rotate_invite(workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    await service.rotate_invite(session, workgroup, user)
    await session.commit()
    return service.workgroup_out(workgroup)


@router.post("/{workgroup_id}/invite/toggle")
async def toggle_invite(body: InviteToggleIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    await service.set_invite_active(session, workgroup, user, body.active)
    await session.commit()
    return service.workgroup_out(workgroup)


@router.post("/{workgroup_id}/invite/email")
async def email_invite(body: InviteEmailIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("invite-email", str(workgroup.id), 1000, 86400)
    emails = sorted({str(e).lower() for e in body.emails})
    for email in emails:
        queue_email(session, email, "staff_invite", {"company": workgroup.name, "manager_name": user.full_name,
                                                     "join_url": service.join_url(workgroup), "message": body.message})
    audit(session, action="invite.emailed", summary=f"Emailed the onboarding link to {len(emails)} staff", actor=user, workgroup_id=workgroup.id)
    await session.commit()
    return {"sent": len(emails)}


@router.get("/{workgroup_id}/activity")
async def activity(workgroup: OwnedWorkgroup, session: SessionDep, page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100),
                   action: str | None = None) -> dict[str, Any]:
    stmt = select(AuditLog).where(AuditLog.workgroup_id == workgroup.id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [service.audit_out(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/{workgroup_id}/analytics")
async def workgroup_analytics(workgroup: OwnedWorkgroup, session: SessionDep, months: int = Query(12, ge=3, le=24)) -> dict[str, Any]:
    return await analytics.workgroup_analytics(session, workgroup, months)
