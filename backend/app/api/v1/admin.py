from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Query, Response

from ...core.errors import NotFound, ValidationFailed
from ...core.money import FeeSchedule
from ...core.redis import revoke_all_refresh_tokens
from ...core.timeutil import utcnow
from ...models import Plan, User
from ...schemas.requests import AdminSettingsIn, AdminUserIn, PlanUpdateIn
from ...services import admin as service
from ...services import billing, mailer, platform
from ...services.activity import audit
from ...services.staff import to_csv
from ..deps import Admin, SessionDep

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
async def overview(_: Admin, session: SessionDep) -> dict[str, Any]:
    return await service.overview(session)


@router.get("/users")
async def users(_: Admin, session: SessionDep, q: str | None = None, status: str | None = None, page: int = Query(1, ge=1),
                page_size: int = Query(25, ge=1, le=100)) -> dict[str, Any]:
    return await service.list_users(session, q, status, page, page_size)


@router.patch("/users/{user_id}")
async def update_user(user_id: uuid.UUID, body: AdminUserIn, admin: Admin, session: SessionDep) -> dict[str, Any]:
    user = await session.get(User, user_id)
    if user is None or user.status in ("deleted", "purged"):
        raise NotFound("User not found.")
    if user.role == "admin":
        raise ValidationFailed("Admin accounts can't be suspended here.")
    user.status = body.status
    if body.status == "suspended":
        user.token_version += 1
        await revoke_all_refresh_tokens(user.id)
    audit(session, action="admin.user_status", summary=f"{admin.full_name} set {user.email} to {body.status}", actor=admin)
    await session.commit()
    return {"id": str(user.id), "status": user.status}


@router.get("/workgroups")
async def workgroups(_: Admin, session: SessionDep, q: str | None = None, page: int = Query(1, ge=1),
                     page_size: int = Query(25, ge=1, le=100)) -> dict[str, Any]:
    return await service.list_workgroups(session, q, page, page_size)


@router.get("/payroll-runs")
async def runs(_: Admin, session: SessionDep, status: str | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(25, ge=1, le=100)) -> dict[str, Any]:
    return await service.list_runs(session, status, page, page_size)


@router.get("/plans")
async def plans(_: Admin, session: SessionDep) -> list[dict[str, Any]]:
    return [billing.plan_out(p) for p in await billing.list_plans(session, include_inactive=True)]


@router.patch("/plans/{code}")
async def update_plan(code: str, body: PlanUpdateIn, admin: Admin, session: SessionDep) -> dict[str, Any]:
    plan = await session.get(Plan, code)
    if plan is None:
        raise NotFound("Plan not found.")
    data = body.model_dump(exclude_unset=True)
    unlimited = data.pop("unlimited", None)
    for key, value in data.items():
        setattr(plan, key, value)
    if unlimited is True:
        plan.max_staff = None
    if plan.max_staff is not None and plan.max_staff < plan.min_staff:
        raise ValidationFailed("Maximum staff must be at least the minimum.")
    audit(session, action="admin.plan_updated", summary=f"{admin.full_name} updated the {plan.name} plan", actor=admin, meta={"changes": data})
    await session.commit()
    return billing.plan_out(plan)


@router.get("/settings")
async def get_settings(_: Admin, session: SessionDep) -> dict[str, Any]:
    return await platform.all_settings(session)


@router.patch("/settings")
async def update_settings(body: AdminSettingsIn, admin: Admin, session: SessionDep) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    if "fees" in data and data["fees"] is not None:
        merged = {**FeeSchedule.from_dict(await platform.get_setting(session, "fees")).to_dict(), **data["fees"]}
        fees = FeeSchedule.from_dict(merged)
        data["fees"] = fees.to_dict()
    if "commission_bps" in data:
        fees = FeeSchedule.from_dict(data.get("fees") or await platform.get_setting(session, "fees"))
        fees.commission_bps = data.pop("commission_bps")
        data["fees"] = fees.to_dict()
    for key, value in data.items():
        await platform.set_setting(session, key, value)
    audit(session, action="admin.settings_updated", summary=f"{admin.full_name} updated platform settings", actor=admin, meta={"keys": list(data)})
    await session.commit()
    return await platform.all_settings(session)


@router.get("/revenue/export")
async def export_revenue(_: Admin, session: SessionDep, days: int = Query(90, ge=1, le=730)) -> Response:
    rows = await service.revenue_ledger(session, days)
    header = ["Date (UTC)", "Source", "Workgroup", "Reference", "Revenue (NGN)", "Salary disbursed (NGN)"]
    return Response(to_csv(header, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="streixpei-revenue-{utcnow():%Y%m%d}.csv"'})


@router.get("/integrity")
async def integrity(_: Admin, session: SessionDep) -> dict[str, Any]:
    return await service.ledger_integrity(session)


@router.post("/emails/retry")
async def retry_emails(_: Admin, session: SessionDep) -> dict[str, int]:
    return {"requeued": await mailer.retry_failed(session)}
