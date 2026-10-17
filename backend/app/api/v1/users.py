from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import func, select, update

from ...core.errors import NotFound, Unauthorized
from ...core.security import verify_password
from ...core.timeutil import utcnow
from ...models import Notification
from ...schemas.requests import ChangePasswordIn, PasswordIn, ProfileIn
from ...services import auth as auth_service
from ...services.activity import audit
from ..deps import CurrentUser, SessionDep, client_ip
from .auth import _clear_cookie, user_out

router = APIRouter(tags=["account"])

ALLOWED_PREFERENCES = {"theme", "accent", "density", "dark_mode", "last_workgroup_id", "dismissed_tips"}


@router.patch("/users/me")
async def update_profile(body: ProfileIn, user: CurrentUser, session: SessionDep) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    for key in ("first_name", "last_name", "phone"):
        if key in data:
            setattr(user, key, data[key])
    if data.get("preferences") is not None:
        prefs = dict(user.preferences or {})
        for key, value in data["preferences"].items():
            if key in ALLOWED_PREFERENCES:
                prefs[key] = value
        user.preferences = prefs
    await session.commit()
    return await user_out(session, user)


@router.post("/users/me/password")
async def change_password(body: ChangePasswordIn, request: Request, user: CurrentUser, session: SessionDep) -> dict[str, str]:
    if not await verify_password(body.current_password, user.password_hash):
        raise Unauthorized("Your current password is incorrect.", code="invalid_password")
    await auth_service.set_password(session, user, body.new_password, client_ip(request))
    await session.commit()
    return {"message": "Password changed. Please sign in again on your other devices."}


@router.post("/users/me/delete", status_code=status.HTTP_200_OK)
async def delete_account(body: PasswordIn, user: CurrentUser, session: SessionDep, response: Response) -> dict[str, str]:
    await auth_service.delete_account(session, user, body.password)
    await session.commit()
    _clear_cookie(response)
    return {"message": "Your account is scheduled for deletion in 30 days. Sign in before then to restore it."}


# ------------------------------------------------------------ notifications
def _note_out(n: Notification) -> dict[str, Any]:
    return {"id": str(n.id), "title": n.title, "body": n.body, "kind": n.kind, "link": n.link,
            "workgroup_id": str(n.workgroup_id) if n.workgroup_id else None, "read": n.read_at is not None, "created_at": n.created_at}


@router.get("/notifications")
async def list_notifications(user: CurrentUser, session: SessionDep, unread: bool = False, page: int = Query(1, ge=1),
                             page_size: int = Query(30, ge=1, le=100)) -> dict[str, Any]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread:
        stmt = stmt.where(Notification.read_at.is_(None))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    unread_count = (
        await session.execute(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    ).scalar_one()
    return {"items": [_note_out(n) for n in rows], "total": total, "unread": unread_count, "page": page, "page_size": page_size}


@router.get("/notifications/unread-count")
async def unread_count(user: CurrentUser, session: SessionDep) -> dict[str, int]:
    count = (
        await session.execute(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    ).scalar_one()
    return {"unread": count}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> dict[str, Any]:
    note = await session.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise NotFound("Notification not found.")
    note.read_at = note.read_at or utcnow()
    await session.commit()
    return _note_out(note)


@router.post("/notifications/read-all")
async def mark_all_read(user: CurrentUser, session: SessionDep) -> dict[str, int]:
    result = await session.execute(
        update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=utcnow())
    )
    await session.commit()
    return {"updated": result.rowcount or 0}
