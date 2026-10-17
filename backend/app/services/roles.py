"""Roles / salary grades: set a salary once for everyone in a role."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import format_naira
from ..models import Role, StaffMember, User, Workgroup
from .activity import audit


def _norm(name: str) -> str:
    return " ".join(name.strip().split()).lower()


async def list_roles(session: AsyncSession, workgroup_id: uuid.UUID) -> list[dict[str, Any]]:
    roles = (await session.execute(select(Role).where(Role.workgroup_id == workgroup_id).order_by(Role.name))).scalars().all()
    counts = dict(
        (
            await session.execute(
                select(StaffMember.role_id, func.count())
                .where(StaffMember.workgroup_id == workgroup_id, StaffMember.status != "inactive", StaffMember.role_id.is_not(None))
                .group_by(StaffMember.role_id)
            )
        ).all()
    )
    return [role_out(r, counts.get(r.id, 0)) for r in roles]


def role_out(role: Role, staff_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(role.id),
        "name": role.name,
        "salary_kobo": role.salary_kobo,
        "description": role.description,
        "staff_count": staff_count,
        "created_at": role.created_at,
    }


async def get_role(session: AsyncSession, workgroup_id: uuid.UUID, role_id: uuid.UUID) -> Role:
    role = await session.get(Role, role_id)
    if role is None or role.workgroup_id != workgroup_id:
        raise NotFound("Role not found.")
    return role


async def find_role(session: AsyncSession, workgroup_id: uuid.UUID, name: str) -> Role | None:
    return (await session.execute(select(Role).where(Role.workgroup_id == workgroup_id, Role.name_norm == _norm(name)))).scalar_one_or_none()


async def create_role(session: AsyncSession, workgroup: Workgroup, actor: User, name: str, salary_kobo: int, description: str | None = None) -> Role:
    name = " ".join(name.strip().split())
    if not name:
        raise ValidationFailed("Give the role a name.")
    if salary_kobo < 0:
        raise ValidationFailed("Salary can't be negative.")
    if await find_role(session, workgroup.id, name):
        raise Conflict(f"A role called “{name}” already exists.")
    role = Role(workgroup_id=workgroup.id, name=name[:80], name_norm=_norm(name)[:80], salary_kobo=salary_kobo, description=description)
    session.add(role)
    await session.flush()
    audit(session, action="role.created", summary=f"Created role {role.name} at {format_naira(salary_kobo)}", actor=actor, workgroup_id=workgroup.id)
    return role


async def update_role(session: AsyncSession, workgroup: Workgroup, role: Role, actor: User, data: dict[str, Any]) -> Role:
    changes = []
    if data.get("name"):
        name = " ".join(data["name"].strip().split())
        existing = await find_role(session, workgroup.id, name)
        if existing and existing.id != role.id:
            raise Conflict(f"A role called “{name}” already exists.")
        role.name, role.name_norm = name[:80], _norm(name)[:80]
        changes.append("name")
    if "salary_kobo" in data and data["salary_kobo"] is not None:
        if data["salary_kobo"] < 0:
            raise ValidationFailed("Salary can't be negative.")
        changes.append(f"salary {format_naira(role.salary_kobo)} → {format_naira(data['salary_kobo'])}")
        role.salary_kobo = data["salary_kobo"]
    if "description" in data:
        role.description = data["description"]
    if changes:
        audit(session, action="role.updated", summary=f"Role {role.name}: {', '.join(changes)}", actor=actor, workgroup_id=workgroup.id)
    return role


async def delete_role(session: AsyncSession, workgroup: Workgroup, role: Role, actor: User) -> None:
    members = (
        (await session.execute(select(StaffMember).where(StaffMember.role_id == role.id))).unique().scalars().all()
    )
    for member in members:
        if member.salary_kobo is None:
            member.salary_kobo = role.salary_kobo  # keep their pay unchanged
        member.role_id = None
    await session.delete(role)
    audit(session, action="role.deleted", summary=f"Deleted role {role.name} ({len(members)} staff kept their salary)", actor=actor, workgroup_id=workgroup.id)
