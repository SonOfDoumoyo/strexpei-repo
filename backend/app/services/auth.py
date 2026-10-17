"""Accounts: registration, verification, login sessions, password reset."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import AppError, Conflict, Forbidden, Unauthorized, ValidationFailed
from ..core.money import bps_label
from ..core.redis import hit_rate_limit, revoke_all_refresh_tokens, store_otp, verify_otp
from ..core.security import (
    DUMMY_PASSWORD_HASH,
    create_signed_token,
    generate_otp,
    hash_password,
    read_signed_token,
    verify_password,
)
from ..core.timeutil import get_tz, utcnow
from ..models import PayrollRun, Subscription, User, Workgroup
from . import platform
from .activity import audit
from .mailer import queue_email

logger = logging.getLogger("streixpei.auth")

VERIFY_TOKEN_MAX_AGE = 24 * 3600
RESET_OTP_TTL = 10 * 60


def normalise_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return (await session.execute(select(User).where(func.lower(User.email) == normalise_email(email)))).scalar_one_or_none()


def _verify_url(user: User) -> str:
    token = create_signed_token("verify_email", {"uid": str(user.id), "email": user.email})
    return f"{settings.FRONTEND_URL}/verify-email?token={token}"


def queue_verification_email(session: AsyncSession, user: User) -> None:
    queue_email(session, user.email, "verify_email", {"name": user.first_name, "verify_url": _verify_url(user)})


async def register(session: AsyncSession, *, first_name: str, last_name: str, email: str, phone: str | None, password: str) -> User:
    email = normalise_email(email)
    existing = await get_user_by_email(session, email)
    if existing is not None:
        if existing.status == "deleted":
            raise Conflict("This email belongs to an account scheduled for deletion. Sign in to restore it.", code="account_deleted")
        raise Conflict("An account with this email already exists. Try signing in instead.", code="email_taken")
    user = User(
        email=email,
        password_hash=await hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone,
        role="manager",
        status="active",
    )
    session.add(user)
    await session.flush()
    queue_verification_email(session, user)
    audit(session, action="auth.registered", summary=f"{user.full_name} created an account", actor=user)
    return user


async def resend_verification(session: AsyncSession, email: str) -> None:
    user = await get_user_by_email(session, email)
    if user and not user.is_verified and user.status == "active":
        queue_verification_email(session, user)


async def verify_email(session: AsyncSession, token: str) -> User:
    data = read_signed_token(token, "verify_email", VERIFY_TOKEN_MAX_AGE)
    if not data:
        raise AppError("This verification link is invalid or has expired. Request a new one.", code="invalid_token")
    user = await session.get(User, data.get("uid"))
    if user is None or normalise_email(user.email) != normalise_email(str(data.get("email", ""))):
        raise AppError("This verification link is no longer valid.", code="invalid_token")
    if user.status != "active":
        raise Forbidden("This account is not active.")
    if not user.is_verified:
        user.email_verified_at = utcnow()
        fees = await platform.get_fees(session)
        queue_email(
            session,
            user.email,
            "welcome",
            {
                "name": user.first_name,
                "dashboard_url": f"{settings.FRONTEND_URL}/app",
                "trial_days": await platform.get_int(session, "trial_days"),
                "commission_percent": bps_label(fees.commission_bps),
            },
        )
        audit(session, action="auth.email_verified", summary=f"{user.full_name} verified their email", actor=user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str, ip: str) -> User:
    email = normalise_email(email)
    await hit_rate_limit("login-ip", ip, 30, 900)
    await hit_rate_limit("login-email", email, 8, 900)
    user = await get_user_by_email(session, email)
    if user is None:
        await verify_password(password, DUMMY_PASSWORD_HASH)  # equalise timing
        raise Unauthorized("Incorrect email or password.", code="invalid_credentials")
    if not await verify_password(password, user.password_hash):
        raise Unauthorized("Incorrect email or password.", code="invalid_credentials")
    if user.status == "suspended":
        raise Forbidden("This account has been suspended. Contact support for help.", code="account_suspended")
    if user.status == "deleted":
        # Signing back in during the grace window restores the account.
        user.status = "active"
        user.deleted_at = None
        user.purge_at = None
        restore = (await session.execute(select(Workgroup).where(Workgroup.owner_id == user.id, Workgroup.status == "archived"))).scalars().all()
        for wg in restore:
            wg.status = "active"
        audit(session, action="auth.account_restored", summary=f"{user.full_name} restored their account", actor=user, ip=ip)
    if not user.is_verified:
        queue_verification_email(session, user)
        await session.commit()
        raise Forbidden(
            "Please confirm your email first. We've sent you a fresh verification link.", code="email_not_verified", details={"email": user.email}
        )
    user.last_login_at = utcnow()
    audit(session, action="auth.login", summary=f"{user.full_name} signed in", actor=user, ip=ip)
    return user


async def start_password_reset(session: AsyncSession, email: str, ip: str) -> None:
    email = normalise_email(email)
    await hit_rate_limit("reset-ip", ip, 10, 3600)
    await hit_rate_limit("reset-email", email, 5, 3600)
    user = await get_user_by_email(session, email)
    if user is None or user.status == "suspended":
        return  # never reveal whether an email exists
    otp = generate_otp()
    await store_otp("reset", email, otp, RESET_OTP_TTL)
    queue_email(session, user.email, "password_reset", {"name": user.first_name, "otp": otp, "minutes": RESET_OTP_TTL // 60})


async def complete_password_reset(session: AsyncSession, email: str, otp: str, new_password: str, ip: str) -> User:
    email = normalise_email(email)
    await hit_rate_limit("reset-verify", email, 10, 900)
    result = await verify_otp("reset", email, otp)
    if result == "expired":
        raise AppError("This code has expired. Request a new one.", code="otp_expired")
    if result == "locked":
        raise AppError("Too many incorrect attempts. Request a new code.", code="otp_locked")
    if result != "ok":
        raise AppError("That code is incorrect.", code="otp_invalid")
    user = await get_user_by_email(session, email)
    if user is None:
        raise AppError("This code has expired. Request a new one.", code="otp_expired")
    await set_password(session, user, new_password, ip)
    if not user.is_verified:
        user.email_verified_at = utcnow()  # proving inbox access verifies the email
    return user


async def set_password(session: AsyncSession, user: User, new_password: str, ip: str | None) -> None:
    if await verify_password(new_password, user.password_hash):
        raise ValidationFailed("Choose a password you haven't used for this account.")
    user.password_hash = await hash_password(new_password)
    user.token_version += 1
    await revoke_all_refresh_tokens(user.id)
    changed_at = utcnow().astimezone(get_tz(settings.TIMEZONE)).strftime("%d %b %Y, %I:%M %p")
    queue_email(session, user.email, "password_changed", {"name": user.first_name, "changed_at": changed_at, "email": user.email})
    audit(session, action="auth.password_changed", summary=f"{user.full_name} changed their password", actor=user, ip=ip)


async def delete_account(session: AsyncSession, user: User, password: str) -> None:
    if not await verify_password(password, user.password_hash):
        raise Unauthorized("Incorrect password.", code="invalid_credentials")
    owned = (await session.execute(select(Workgroup).where(Workgroup.owner_id == user.id, Workgroup.status == "active"))).unique().scalars().all()
    funded = [wg.name for wg in owned if wg.wallet_balance_kobo > 0]
    if funded:
        raise Conflict(
            f"Withdraw the money in {', '.join(funded)} before deleting your account. Open Wallet and choose Withdraw.",
            code="wallet_not_empty",
            details={"workgroups": funded},
        )
    from .withdrawals import in_flight

    busy = (
        await session.execute(
            select(func.count()).select_from(PayrollRun).where(PayrollRun.workgroup_id.in_([wg.id for wg in owned]), PayrollRun.status == "processing")
        )
    ).scalar_one() if owned else 0
    if busy or await in_flight(session, [wg.id for wg in owned]):
        raise Conflict("Wait for payments in progress to finish before deleting your account.")
    now = utcnow()
    user.status = "deleted"
    user.deleted_at = now
    user.purge_at = now + timedelta(days=30)
    user.token_version += 1
    workgroups = (await session.execute(select(Workgroup).where(Workgroup.owner_id == user.id))).scalars().all()
    for wg in workgroups:
        wg.status = "archived"
        wg.invite_active = False
        sub = (await session.execute(select(Subscription).where(Subscription.workgroup_id == wg.id))).scalar_one_or_none()
        if sub:
            sub.auto_renew = False
    await revoke_all_refresh_tokens(user.id)
    audit(session, action="auth.account_deleted", summary=f"{user.full_name} scheduled their account for deletion", actor=user)


async def purge_deleted_users(session: AsyncSession) -> int:
    """Anonymises accounts 30 days after deletion.

    Personal data is scrubbed, but payroll and ledger records stay (they are
    the employer's financial records). Accounts still holding wallet money
    are left for manual review.
    """
    now = utcnow()
    users = (await session.execute(select(User).where(User.status == "deleted", User.purge_at <= now))).scalars().all()
    purged = 0
    for user in users:
        held = (
            await session.execute(select(func.coalesce(func.sum(Workgroup.wallet_balance_kobo), 0)).where(Workgroup.owner_id == user.id))
        ).scalar_one()
        if held and held > 0:
            logger.warning("Not purging user %s: %s kobo still held in wallets", user.id, held)
            continue
        user.email = f"deleted-{user.id.hex}@deleted.invalid"
        user.first_name = "Deleted"
        user.last_name = "user"
        user.phone = None
        user.password_hash = await hash_password(generate_otp(32))
        user.purge_at = None
        user.status = "purged"
        purged += 1
    await session.commit()
    return purged


async def ensure_admin(session: AsyncSession) -> None:
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return
    user = await get_user_by_email(session, settings.ADMIN_EMAIL)
    if user is None:
        session.add(
            User(
                email=normalise_email(settings.ADMIN_EMAIL),
                password_hash=await hash_password(settings.ADMIN_PASSWORD),
                first_name="Platform",
                last_name="Admin",
                role="admin",
                status="active",
                email_verified_at=utcnow(),
            )
        )
        logger.info("Created admin account %s", settings.ADMIN_EMAIL)
    elif user.role != "admin":
        user.role = "admin"
    await session.commit()
