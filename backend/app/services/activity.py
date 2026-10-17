"""In-app notifications and the audit trail."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Notification, User


def notify(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    *,
    kind: str = "info",
    link: str | None = None,
    workgroup_id: uuid.UUID | None = None,
) -> Notification:
    notification = Notification(user_id=user_id, title=title, body=body, kind=kind, link=link, workgroup_id=workgroup_id)
    session.add(notification)
    return notification


def audit(
    session: AsyncSession,
    *,
    action: str,
    summary: str,
    actor: User | None = None,
    actor_label: str | None = None,
    workgroup_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor.id if actor else None,
        actor_label=actor_label or (actor.full_name if actor else "Streixpei"),
        workgroup_id=workgroup_id,
        action=action,
        summary=summary[:255],
        meta=meta or {},
        ip=ip,
    )
    session.add(log)
    return log
