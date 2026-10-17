from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.errors import Unauthorized
from ...core.redis import block_access_token, hit_rate_limit, issue_refresh_token, revoke_refresh_token, rotate_refresh_token
from ...core.security import create_access_token, decode_access_token
from ...models import Subscription, User, Workgroup
from ...schemas.requests import EmailIn, LoginIn, RegisterIn, ResetPasswordIn, TokenIn
from ...services import auth as auth_service
from ..deps import CurrentUser, SessionDep, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "spx_rt"
COOKIE_PATH = "/api/v1/auth"


def _set_cookie(response: Response, token: str, ttl: int, remember: bool) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=ttl if remember else None,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=COOKIE_PATH,
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, domain=settings.COOKIE_DOMAIN, secure=settings.cookie_secure,
                           httponly=True, samesite=settings.COOKIE_SAMESITE)


async def user_out(session: AsyncSession, user: User) -> dict[str, Any]:
    paid = False
    workgroup_count = 0
    if user.role == "manager":
        workgroup_count = (
            await session.execute(select(func.count()).select_from(Workgroup).where(Workgroup.owner_id == user.id, Workgroup.status == "active"))
        ).scalar_one()
        paid = (
            await session.execute(
                select(func.count()).select_from(Subscription).join(Workgroup, Workgroup.id == Subscription.workgroup_id)
                .where(Workgroup.owner_id == user.id, Subscription.status.in_(["active", "past_due"]))
            )
        ).scalar_one() > 0
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "status": user.status,
        "verified": user.is_verified,
        "has_paid_plan": paid,
        "workgroup_count": int(workgroup_count),
        "preferences": user.preferences or {},
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


async def _session_response(session: AsyncSession, response: Response, user: User, remember: bool, request: Request) -> dict[str, Any]:
    access, _ = create_access_token(user.id, user.role, user.token_version)
    refresh, ttl = await issue_refresh_token(user.id, remember, meta={"ua": (request.headers.get("user-agent") or "")[:120]})
    _set_cookie(response, refresh, ttl, remember)
    return {"access_token": access, "token_type": "bearer", "expires_in": settings.ACCESS_TOKEN_TTL_MINUTES * 60, "user": await user_out(session, user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, request: Request, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("register-ip", client_ip(request), 10, 3600)
    user = await auth_service.register(
        session, first_name=body.first_name, last_name=body.last_name, email=body.email, phone=body.phone, password=body.password
    )
    await session.commit()
    return {"message": "Account created. Check your email to confirm your address.", "email": user.email}


@router.post("/verify-email")
async def verify_email(body: TokenIn, request: Request, response: Response, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("verify-ip", client_ip(request), 30, 3600)
    user = await auth_service.verify_email(session, body.token)
    await session.commit()
    return await _session_response(session, response, user, True, request)


@router.post("/resend-verification")
async def resend_verification(body: EmailIn, request: Request, session: SessionDep) -> dict[str, str]:
    await hit_rate_limit("resend-ip", client_ip(request), 10, 3600)
    await hit_rate_limit("resend-email", body.email.lower(), 3, 900)
    await auth_service.resend_verification(session, body.email)
    await session.commit()
    return {"message": "If that account needs confirming, a new link is on its way."}


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response, session: SessionDep) -> dict[str, Any]:
    user = await auth_service.authenticate(session, body.email, body.password, client_ip(request))
    await session.commit()
    return await _session_response(session, response, user, body.remember_me, request)


@router.post("/refresh")
async def refresh(request: Request, response: Response, session: SessionDep) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise Unauthorized("No active session.", code="no_session")
    rotated = await rotate_refresh_token(token)
    if rotated is None:
        _clear_cookie(response)
        raise Unauthorized("Your session has ended. Please sign in again.", code="session_expired")
    record, new_token, ttl = rotated
    user = await session.get(User, record.user_id)
    if user is None or user.status != "active" or not user.is_verified:
        await revoke_refresh_token(new_token)
        _clear_cookie(response)
        raise Unauthorized("Your session has ended. Please sign in again.", code="session_expired")
    remember = bool(record.get("remember"))
    _set_cookie(response, new_token, ttl, remember)
    access, _ = create_access_token(user.id, user.role, user.token_version)
    return {"access_token": access, "token_type": "bearer", "expires_in": settings.ACCESS_TOKEN_TTL_MINUTES * 60, "user": await user_out(session, user)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> Response:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        await revoke_refresh_token(token)
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        payload = decode_access_token(authorization.split(" ", 1)[1])
        if payload:
            await block_access_token(payload["jti"], payload["exp"])
    result = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(result)
    return result


@router.post("/forgot-password")
async def forgot_password(body: EmailIn, request: Request, session: SessionDep) -> dict[str, str]:
    await auth_service.start_password_reset(session, body.email, client_ip(request))
    await session.commit()
    return {"message": "If an account exists for that email, we've sent a 6-digit code."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordIn, request: Request, session: SessionDep) -> dict[str, str]:
    await auth_service.complete_password_reset(session, body.email, body.otp, body.password, client_ip(request))
    await session.commit()
    return {"message": "Password updated. You can sign in with your new password."}


@router.get("/me")
async def me(user: CurrentUser, session: SessionDep) -> dict[str, Any]:
    return await user_out(session, user)
