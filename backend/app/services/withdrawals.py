"""Wallet withdrawals: a manager sends wallet money back to a bank account.

The flow mirrors a single payroll transfer:

1. The destination account is resolved with the bank and a Paystack transfer
   recipient is created (outside any database lock).
2. Under the workgroup row lock the wallet is debited for the amount plus
   Paystack's transfer fee and a ``withdrawals`` row is written as ``queued``.
3. The transfer is sent. Its outcome — from the immediate response, the
   ``transfer.*`` webhook or the reconciler — goes through ``apply_update``,
   which is idempotent. A failed or reversed transfer refunds the amount and
   the fee to the wallet.

No Streixpei service fee is charged: it is the customer's own money.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import AppError, InsufficientFunds, NotFound, ServiceUnavailable, ValidationFailed
from ..core.ids import WITHDRAWAL_PREFIX, human_number, withdrawal_reference
from ..core.money import format_naira
from ..core.redis import redis_lock
from ..core.timeutil import utcnow
from ..models import User, Withdrawal, Workgroup
from . import platform, wallet
from .activity import audit, notify
from .mailer import mask_account, queue_email
from .paystack import PaystackError, get_provider
from .staff import verify_bank_account

logger = logging.getLogger("streixpei.withdrawals")

MIN_WITHDRAWAL_KOBO = 1_000_00
MAX_WITHDRAWAL_KOBO = 50_000_000_00
TERMINAL = {"success", "failed", "reversed"}


def is_withdrawal_reference(reference: str | None) -> bool:
    return bool(reference) and str(reference).startswith(WITHDRAWAL_PREFIX)


def withdrawal_out(w: Withdrawal) -> dict[str, Any]:
    return {
        "id": str(w.id),
        "number": w.number,
        "amount_kobo": w.amount_kobo,
        "fee_kobo": w.fee_kobo,
        "total_kobo": w.amount_kobo + w.fee_kobo,
        "bank_code": w.bank_code,
        "bank_name": w.bank_name,
        "account_number": w.account_number,
        "account_number_masked": mask_account(w.account_number),
        "account_name": w.account_name,
        "status": w.status,
        "failure_reason": w.failure_reason,
        "refunded": w.refunded,
        "reference": w.reference,
        "created_at": w.created_at,
        "completed_at": w.completed_at,
    }


async def quote(session: AsyncSession, workgroup: Workgroup, amount_kobo: int) -> dict[str, Any]:
    fees = await platform.get_fees(session)
    fee = fees.transfer_fee(amount_kobo)
    total = amount_kobo + fee
    # The most that can be withdrawn so that amount + its own fee fits the balance.
    balance = workgroup.wallet_balance_kobo
    max_amount = 0
    candidate = balance
    for _ in range(8):  # fee bands are few; this converges in two or three steps
        candidate = balance - fees.transfer_fee(candidate)
        if candidate > 0 and candidate + fees.transfer_fee(candidate) <= balance:
            max_amount = max(max_amount, candidate)
    return {
        "amount_kobo": amount_kobo,
        "fee_kobo": fee,
        "total_kobo": total,
        "balance_kobo": balance,
        "max_amount_kobo": max_amount,
        "min_amount_kobo": MIN_WITHDRAWAL_KOBO,
        "enough": total <= balance,
    }


async def resolve(account_number: str, bank_code: str) -> dict[str, str]:
    account_name, bank_name = await verify_bank_account(account_number, bank_code)
    return {"account_name": account_name, "bank_name": bank_name, "account_number": re.sub(r"\D", "", account_number)}


async def list_for(session: AsyncSession, workgroup_id: uuid.UUID, page: int, page_size: int) -> dict[str, Any]:
    stmt = select(Withdrawal).where(Withdrawal.workgroup_id == workgroup_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Withdrawal.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [withdrawal_out(w) for w in rows], "total": total, "page": page, "page_size": page_size}


async def in_flight(session: AsyncSession, workgroup_ids: list[uuid.UUID]) -> int:
    if not workgroup_ids:
        return 0
    return (
        await session.execute(
            select(func.count()).select_from(Withdrawal).where(Withdrawal.workgroup_id.in_(workgroup_ids), Withdrawal.status.in_(["queued", "processing"]))
        )
    ).scalar_one()


async def create(
    session: AsyncSession, workgroup_id: uuid.UUID, user: User, *, amount_kobo: int, bank_code: str, account_number: str
) -> Withdrawal:
    if amount_kobo < MIN_WITHDRAWAL_KOBO:
        raise ValidationFailed(f"The smallest withdrawal is {format_naira(MIN_WITHDRAWAL_KOBO)}.")
    if amount_kobo > MAX_WITHDRAWAL_KOBO:
        raise ValidationFailed(f"The largest single withdrawal is {format_naira(MAX_WITHDRAWAL_KOBO)}. Split it into smaller amounts.")
    provider = get_provider()
    account_number = re.sub(r"\D", "", account_number or "")

    async with redis_lock(f"withdraw:{workgroup_id}", ttl_seconds=120) as acquired:
        if not acquired:
            raise AppError("Another withdrawal is being set up for this workgroup. Try again in a moment.", code="withdrawal_in_progress", status_code=409)

        # Phase 0: everything that talks to Paystack happens before any lock.
        account_name, bank_name = await verify_bank_account(account_number, bank_code)
        fees = await platform.get_fees(session)
        fee = fees.transfer_fee(amount_kobo)
        try:
            platform_balance = await provider.get_balance()
        except PaystackError as exc:
            raise ServiceUnavailable("We couldn't reach Paystack. Please try again in a few minutes.") from exc
        if platform_balance < amount_kobo + fee:
            from .payroll import _alert_admin

            await _alert_admin(
                session,
                "Paystack balance too low for a withdrawal",
                f"A withdrawal of {format_naira(amount_kobo)} needs {format_naira(amount_kobo + fee)} in the Paystack balance "
                f"but only {format_naira(platform_balance)} is available.",
            )
            await session.commit()
            raise ServiceUnavailable("Withdrawals are temporarily unavailable. Our team has been alerted and your money is safe in the wallet.",
                                     code="platform_balance_low")
        try:
            recipient = await provider.create_recipient(account_name, account_number, bank_code)
        except PaystackError as exc:
            raise ServiceUnavailable("We couldn't set up the transfer to that account. Please try again shortly.") from exc
        await session.rollback()  # release the read snapshot before locking

        # Phase 1: lock, check the balance, debit, record.
        workgroup = await wallet.lock_workgroup(session, workgroup_id)
        if workgroup.status != "active":
            raise ValidationFailed("This workgroup is closed.")
        total = amount_kobo + fee
        if workgroup.wallet_balance_kobo < total:
            raise InsufficientFunds(
                f"The wallet has {format_naira(workgroup.wallet_balance_kobo)}. Withdrawing {format_naira(amount_kobo)} "
                f"needs {format_naira(total)} including the {format_naira(fee)} transfer fee.",
                details={"balance_kobo": workgroup.wallet_balance_kobo, "needed_kobo": total},
            )
        w = Withdrawal(
            id=uuid.uuid4(),
            workgroup_id=workgroup.id,
            requested_by_id=user.id,
            number=human_number("WDR"),
            amount_kobo=amount_kobo,
            fee_kobo=fee,
            bank_code=bank_code,
            bank_name=bank_name,
            account_number=account_number,
            account_name=account_name,
            recipient_code=recipient,
            reference=withdrawal_reference(),
            status="queued",
        )
        session.add(w)
        await session.flush()
        where = f"{bank_name} {mask_account(account_number)}"
        await wallet.debit(session, workgroup, amount_kobo, "withdrawal", f"Withdrawal {w.number} to {where}",
                           reference=f"wd:{w.id}", meta={"withdrawal_id": str(w.id)})
        if fee:
            await wallet.debit(session, workgroup, fee, "transfer_fees", f"Paystack transfer fee · withdrawal {w.number}",
                               reference=f"wd:{w.id}:fee", meta={"withdrawal_id": str(w.id)})
        audit(session, action="wallet.withdrawal_requested", summary=f"Withdrew {format_naira(amount_kobo)} to {account_name} ({where})",
              actor=user, workgroup_id=workgroup.id, meta={"withdrawal_id": str(w.id), "amount_kobo": amount_kobo, "fee_kobo": fee})
        await session.commit()
        withdrawal_id = w.id

        # Phase 2: send.
        await send(session, withdrawal_id)
        return await session.get(Withdrawal, withdrawal_id, populate_existing=True)


async def send(session: AsyncSession, withdrawal_id: uuid.UUID) -> None:
    provider = get_provider()
    w = await session.get(Withdrawal, withdrawal_id, populate_existing=True)
    if w is None or w.status != "queued":
        return
    payload = [{"amount": w.amount_kobo, "recipient": w.recipient_code, "reference": w.reference, "reason": f"{settings.APP_NAME} wallet withdrawal"}]
    try:
        results = await provider.bulk_transfer(payload)
    except PaystackError as exc:
        if exc.transient:
            w.status = "processing"
            w.needs_verification = True
            await session.commit()
            return
        logger.error("Withdrawal %s rejected: %s", w.number, exc.message)
        await apply_update(session, w.reference, "failed", f"Transfer rejected: {exc.message}"[:255], None)
        await session.commit()
        return
    result = next((r for r in results if r.reference == w.reference), None)
    if result is None:
        await apply_update(session, w.reference, "processing", None, None, needs_verification=True)
    else:
        if result.status == "otp":
            from .payroll import _alert_admin

            await _alert_admin(session, "Paystack transfers need OTP", "Disable 'Confirm transfers with OTP' in the Paystack dashboard so withdrawals and payroll can run.")
        await apply_update(session, w.reference, result.status, result.reason, result.transfer_code)
    await session.commit()


async def apply_update(
    session: AsyncSession, reference: str, status: str, reason: str | None, transfer_code: str | None, *, needs_verification: bool = False
) -> Withdrawal | None:
    """Single place where a withdrawal's outcome is decided. Idempotent."""
    w = (
        await session.execute(select(Withdrawal).where(Withdrawal.reference == reference).with_for_update().execution_options(populate_existing=True))
    ).scalar_one_or_none()
    if w is None:
        return None
    status = (status or "").lower()
    if transfer_code and not w.transfer_code:
        w.transfer_code = transfer_code

    if status == "success":
        if w.status in TERMINAL:
            return w
        w.status = "success"
        w.failure_reason = None
        w.needs_verification = False
        w.completed_at = utcnow()
        await _tell_owner(session, w, "success")
    elif status in ("failed", "reversed"):
        if w.status in ("failed", "reversed"):
            return w
        if w.status == "success" and status != "reversed":
            return w
        w.status = status
        w.failure_reason = (reason or ("Transfer reversed by the bank" if status == "reversed" else "The receiving bank declined the transfer"))[:255]
        w.needs_verification = False
        w.completed_at = utcnow()
        await _refund(session, w)
        await _tell_owner(session, w, "failed")
    else:
        if w.status in TERMINAL:
            return w
        w.status = "processing"
        if needs_verification:
            w.needs_verification = True
    await session.flush()
    return w


async def _refund(session: AsyncSession, w: Withdrawal) -> None:
    if w.refunded:
        return
    workgroup = await wallet.lock_workgroup(session, w.workgroup_id)
    await wallet.credit(session, workgroup, w.amount_kobo + w.fee_kobo, "refund", f"Refund · withdrawal {w.number} did not go through",
                        reference=f"refund:{w.reference}", meta={"withdrawal_id": str(w.id), "amount_kobo": w.amount_kobo, "fee_kobo": w.fee_kobo})
    w.refunded = True


async def _tell_owner(session: AsyncSession, w: Withdrawal, outcome: str) -> None:
    workgroup = await session.get(Workgroup, w.workgroup_id)
    owner = workgroup.owner
    where = f"{w.bank_name} {mask_account(w.account_number)}"
    if outcome == "success":
        title = f"{format_naira(w.amount_kobo)} sent to {where}"
        body = f"Withdrawal {w.number} from {workgroup.name} was accepted by the bank."
        headline = f"Withdrawal complete: {format_naira(w.amount_kobo)} sent to your bank"
    else:
        title = f"Withdrawal {w.number} didn't go through"
        body = f"{format_naira(w.amount_kobo + w.fee_kobo)} is back in the {workgroup.name} wallet. {w.failure_reason or ''}".strip()
        headline = f"Withdrawal {w.number} was not completed — funds returned"
    notify(session, owner.id, title, body, kind="success" if outcome == "success" else "warning", link="/app/wallet", workgroup_id=workgroup.id)
    queue_email(
        session,
        owner.email,
        "withdrawal_update",
        {
            "headline": headline,
            "outcome": outcome,
            "name": owner.first_name,
            "company": workgroup.name,
            "number": w.number,
            "amount": w.amount_kobo,
            "fee": w.fee_kobo,
            "bank_name": w.bank_name,
            "account_name": w.account_name,
            "account_masked": mask_account(w.account_number),
            "reason": w.failure_reason if outcome != "success" else None,
            "reference": w.reference,
            "date": utcnow().strftime("%d %b %Y, %H:%M UTC"),
            "link": f"{settings.FRONTEND_URL}/app/wallet",
        },
    )
    audit(session, action=f"wallet.withdrawal_{'completed' if outcome == 'success' else 'failed'}",
          summary=f"Withdrawal {w.number} {'completed' if outcome == 'success' else 'failed and was refunded'}",
          actor_label=settings.APP_NAME, workgroup_id=workgroup.id, meta={"withdrawal_id": str(w.id)})


async def reconcile(session: AsyncSession) -> int:
    """Settles withdrawals whose webhook never arrived, and resends ones the
    server stopped before sending (after checking Paystack doesn't have them)."""
    provider = get_provider()
    now = utcnow()
    settled = 0
    stale = (
        await session.execute(
            select(Withdrawal.reference, Withdrawal.updated_at).where(
                Withdrawal.status == "processing", Withdrawal.updated_at < now - timedelta(minutes=10)
            ).limit(200)
        )
    ).all()
    for reference, updated_at in stale:
        try:
            result = await provider.verify_transfer(reference)
        except PaystackError:
            continue
        if result is None:
            if updated_at < now - timedelta(minutes=30):
                await apply_update(session, reference, "failed", "Transfer was not accepted by Paystack", None)
                settled += 1
        elif result.status in TERMINAL:
            await apply_update(session, reference, result.status, result.reason, result.transfer_code)
            settled += 1
        else:
            w = (await session.execute(select(Withdrawal).where(Withdrawal.reference == reference))).scalar_one()
            w.updated_at = now
        await session.commit()

    stuck = (
        await session.execute(
            select(Withdrawal.id, Withdrawal.workgroup_id, Withdrawal.reference).where(
                Withdrawal.status == "queued", Withdrawal.updated_at < now - timedelta(minutes=2)
            ).limit(100)
        )
    ).all()
    for withdrawal_id, workgroup_id, reference in stuck:
        async with redis_lock(f"withdraw:{workgroup_id}", ttl_seconds=120) as acquired:
            if not acquired:
                continue
            try:
                result = await provider.verify_transfer(reference)
            except PaystackError:
                continue
            if result is not None:
                await apply_update(session, reference, result.status, result.reason, result.transfer_code)
                await session.commit()
                settled += 1
            else:
                await send(session, withdrawal_id)
                settled += 1
    return settled


async def get_for(session: AsyncSession, workgroup_id: uuid.UUID, withdrawal_id: uuid.UUID) -> Withdrawal:
    w = await session.get(Withdrawal, withdrawal_id)
    if w is None or w.workgroup_id != workgroup_id:
        raise NotFound("Withdrawal not found.")
    return w
