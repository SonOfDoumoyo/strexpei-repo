from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.errors import Forbidden, Unauthorized
from ..core.redis import is_access_token_blocked
from ..core.security import decode_access_token
from ..models import User, Workgroup
from ..services import workgroups as workgroup_service

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def get_token_payload(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized()
    payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    if payload is None:
        raise Unauthorized("Your session has expired. Please sign in again.", code="token_invalid")
    if await is_access_token_blocked(payload["jti"]):
        raise Unauthorized("Your session has ended. Please sign in again.", code="token_revoked")
    return payload


async def get_current_user(session: SessionDep, payload: Annotated[dict, Depends(get_token_payload)]) -> User:
    try:
        user = await session.get(User, uuid.UUID(payload["sub"]))
    except (ValueError, KeyError):
        raise Unauthorized(code="token_invalid")
    if user is None or user.token_version != payload.get("tv"):
        raise Unauthorized("Your session has ended. Please sign in again.", code="token_revoked")
    if user.status == "suspended":
        raise Forbidden("This account has been suspended. Contact support for help.", code="account_suspended")
    if user.status != "active":
        raise Unauthorized("This account is no longer active.", code="account_inactive")
    if not user.is_verified:
        raise Forbidden("Please confirm your email first.", code="email_not_verified")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_manager(user: CurrentUser) -> User:
    if user.role != "manager":
        raise Forbidden("This area is for finance managers.")
    return user


async def get_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise Forbidden("Admins only.")
    return user


Manager = Annotated[User, Depends(get_manager)]
Admin = Annotated[User, Depends(get_admin)]


async def get_workgroup(workgroup_id: uuid.UUID, session: SessionDep, user: Manager) -> Workgroup:
    return await workgroup_service.get_owned(session, user, workgroup_id)


OwnedWorkgroup = Annotated[Workgroup, Depends(get_workgroup)]
