"""Payroll runs: review → fund → disburse → confirm.

State machine::

    draft ──submit──▶ ready ─────────────disburse──▶ processing ──▶ completed
      │                ▲                                   │      ├▶ partially_failed
      └──submit──▶ awaiting_funding ──(money arrives)──────┘      └▶ failed
    (draft / awaiting_funding / ready) ──cancel──▶ canceled

Money: at disbursement the wallet is debited for salaries + Paystack
transfer fees + the Streixpei commission. Each staff payment is a Paystack
transfer with a unique reference. A failed or reversed transfer refunds that
staff member's salary, fee and commission to the wallet.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import AppError, Conflict, InsufficientFunds, NotFound, ServiceUnavailable, ValidationFailed
from ..core.ids import human_number, transfer_reference
from ..core.money import PayoutBreakdown, bps_label, format_naira
from ..core.redis import redis_lock
from ..core.timeutil import next_payday, period_for, utcnow
from ..models import Payment, PayrollItem, PayrollRun, StaffMember, User, Workgroup
from . import billing, platform, wallet
from .activity import audit, notify
from .mailer import mask_account, queue_email
from .paystack import PaystackError, get_provider

logger = logging.getLogger("streixpei.payroll")

TERMINAL_ITEM = {"success", "failed", "reversed"}
OPEN_ITEM = {"pending", "queued", "processing"}
EDITABLE_RUN = {"draft", "awaiting_funding", "ready"}
BATCH_SIZE = 100


# ------------------------------------------------------------ serializers
def item_out(item: PayrollItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "staff_id": str(item.staff_id) if item.staff_id else None,
        "staff_code": item.staff_code,
        "staff_name": item.staff_name,
        "role_name": item.role_name,
        "bank_name": item.bank_name,
        "account_number_masked": mask_account(item.account_number),
        "account_name": item.account_name,
        "amount_kobo": item.amount_kobo,
        "fee_kobo": item.fee_kobo,
        "commission_kobo": item.commission_kobo,
        "status": item.status,
        "reference": item.reference,
        "failure_reason": item.failure_reason,
        "refunded": item.refunded,
        "paid_at": item.paid_at,
    }


def run_out(run: PayrollRun, items: list[PayrollItem] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(run.id),
        "number": run.number,
        "workgroup_id": str(run.workgroup_id),
        "status": run.status,
        "trigger": run.trigger,
        "period_key": run.period_key,
        "period_label": run.period_label,
        "note": run.note,
        "staff_count": run.staff_count,
        "salaries_kobo": run.salaries_kobo,
        "transfer_fees_kobo": run.transfer_fees_kobo,
        "commission_kobo": run.commission_kobo,
        "commission_bps": run.commission_bps,
        "commission_label": bps_label(run.commission_bps),
        "total_kobo": run.total_kobo,
        "paid_kobo": run.paid_kobo,
        "refunded_kobo": run.refunded_kobo,
        "created_at": run.created_at,
        "submitted_at": run.submitted_at,
        "funded_at": run.funded_at,
        "disbursed_at": run.disbursed_at,
        "completed_at": run.completed_at,
        "canceled_at": run.canceled_at,
        "failure_reason": run.failure_reason,
    }
    if items is not None:
        counts = Counter(i.status for i in items)
        data["items"] = [item_out(i) for i in items]
        data["progress"] = {
            "success": counts.get("success", 0),
            "failed": counts.get("failed", 0) + counts.get("reversed", 0),
            "processing": counts.get("processing", 0) + counts.get("queued", 0),
            "pending": counts.get("pending", 0),
            "total": len(items),
        }
    return data


async def load_items(session: AsyncSession, run_id: uuid.UUID) -> list[PayrollItem]:
    return list(
        (await session.execute(select(PayrollItem).where(PayrollItem.run_id == run_id).order_by(PayrollItem.staff_name))).scalars().all()
    )


async def get_run(session: AsyncSession, workgroup_id: uuid.UUID, run_id: uuid.UUID, *, lock: bool = False) -> PayrollRun:
    stmt = select(PayrollRun).where(PayrollRun.id == run_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None or run.workgroup_id != workgroup_id:
        raise NotFound("Payroll run not found.")
    return run


# ---------------------------------------------------------------- preview
async def _registered_staff(session: AsyncSession, workgroup_id: uuid.UUID, staff_ids: list[uuid.UUID] | None = None) -> list[StaffMember]:
    stmt = select(StaffMember).where(StaffMember.workgroup_id == workgroup_id, StaffMember.status == "registered")
    if staff_ids:
        stmt = stmt.where(StaffMember.id.in_(staff_ids))
    return list((await session.execute(stmt)).unique().scalars().all())


def _not_ready_reasons(member: StaffMember) -> list[str]:
    reasons = []
    if member.effective_salary_kobo <= 0:
        reasons.append("No salary set")
    if not member.bank_verified_at or not member.paystack_recipient_code:
        reasons.append("Bank account not verified")
    return reasons


async def preview(session: AsyncSession, workgroup: Workgroup) -> dict[str, Any]:
    fees = await platform.get_fees(session)
    staff = await _registered_staff(session, workgroup.id)
    breakdown = PayoutBreakdown()
    items, not_ready = [], []
    for member in sorted(staff, key=lambda m: m.display_name.lower()):
        if member.payout_ready:
            fee, commission = breakdown.add(member.effective_salary_kobo, fees)
            items.append({
                "staff_id": str(member.id), "staff_code": member.staff_code, "staff_name": member.display_name,
                "role_name": member.role.name if member.role else None, "bank_name": member.bank_name,
                "account_number_masked": mask_account(member.account_number), "amount_kobo": member.effective_salary_kobo,
                "fee_kobo": fee, "commission_kobo": commission, "name_match": member.name_match,
            })
        else:
            not_ready.append({"staff_id": str(member.id), "staff_code": member.staff_code, "staff_name": member.display_name,
                              "reasons": _not_ready_reasons(member)})
    pending = (
        await session.execute(
            select(func.count()).select_from(StaffMember).where(StaffMember.workgroup_id == workgroup.id, StaffMember.status == "pending")
        )
    ).scalar_one()
    totals = breakdown.as_dict()
    return {
        "items": items,
        "not_ready": not_ready,
        "unregistered_count": int(pending),
        **totals,
        "commission_bps": fees.commission_bps,
        "commission_label": bps_label(fees.commission_bps),
        "wallet_balance_kobo": workgroup.wallet_balance_kobo,
        "shortfall_kobo": max(0, totals["total_kobo"] - workgroup.wallet_balance_kobo),
    }


# ------------------------------------------------------------- lifecycle
async def create_run(
    session: AsyncSession,
    workgroup: Workgroup,
    actor: User | None,
    *,
    trigger: str = "manual",
    staff_ids: list[uuid.UUID] | None = None,
    note: str | None = None,
    period_moment=None,
) -> PayrollRun:
    await billing.require_usable(session, workgroup)
    fees = await platform.get_fees(session)
    staff = [m for m in await _registered_staff(session, workgroup.id, staff_ids) if m.payout_ready]
    if not staff:
        raise ValidationFailed(
            "No staff are ready to be paid. Staff need to register their bank details and have a salary set.", code="no_payable_staff"
        )
    period_key, period_label = period_for(period_moment or utcnow(), workgroup.timezone)
    run = PayrollRun(
        workgroup_id=workgroup.id,
        number=human_number("PAY"),
        created_by_id=actor.id if actor else None,
        trigger=trigger,
        status="draft",
        period_key=period_key,
        period_label=period_label,
        note=(note or "").strip() or None,
        commission_bps=fees.commission_bps,
    )
    session.add(run)
    await session.flush()
    breakdown = PayoutBreakdown()
    for member in staff:
        fee, commission = breakdown.add(member.effective_salary_kobo, fees)
        session.add(
            PayrollItem(
                run_id=run.id,
                workgroup_id=workgroup.id,
                staff_id=member.id,
                staff_code=member.staff_code,
                staff_name=member.display_name,
                staff_email=member.email,
                role_name=member.role.name if member.role else None,
                bank_name=member.bank_name,
                account_number=member.account_number,
                account_name=member.account_name,
                recipient_code=member.paystack_recipient_code,
                amount_kobo=member.effective_salary_kobo,
                fee_kobo=fee,
                commission_kobo=commission,
                reference=transfer_reference(),
            )
        )
    _apply_totals(run, breakdown, len(staff))
    await session.flush()
    audit(
        session,
        action="payroll.created",
        summary=f"Prepared payroll {run.number} for {run.staff_count} staff ({format_naira(run.total_kobo)})",
        actor=actor,
        actor_label=None if actor else "Automatic payday",
        workgroup_id=workgroup.id,
        meta={"run_id": str(run.id), "trigger": trigger},
    )
    return run


def _apply_totals(run: PayrollRun, breakdown: PayoutBreakdown, count: int) -> None:
    run.staff_count = count
    run.salaries_kobo = breakdown.salaries_kobo
    run.transfer_fees_kobo = breakdown.transfer_fees_kobo
    run.commission_kobo = breakdown.commission_kobo
    run.total_kobo = breakdown.total_kobo


def _recompute(run: PayrollRun, items: list[PayrollItem]) -> None:
    breakdown = PayoutBreakdown(
        salaries_kobo=sum(i.amount_kobo for i in items),
        transfer_fees_kobo=sum(i.fee_kobo for i in items),
        commission_kobo=sum(i.commission_kobo for i in items),
    )
    _apply_totals(run, breakdown, len(items))


async def remove_item(session: AsyncSession, workgroup: Workgroup, run: PayrollRun, item_id: uuid.UUID, actor: User) -> PayrollRun:
    if run.status not in EDITABLE_RUN:
        raise Conflict("This payroll has already been disbursed and can't be edited.")
    items = await load_items(session, run.id)
    target = next((i for i in items if i.id == item_id), None)
    if target is None:
        raise NotFound("That staff member isn't in this payroll.")
    await session.delete(target)
    remaining = [i for i in items if i.id != item_id]
    _recompute(run, remaining)
    if not remaining:
        run.status = "canceled"
        run.canceled_at = utcnow()
    elif run.status == "ready" and workgroup.wallet_balance_kobo < run.total_kobo:
        run.status = "awaiting_funding"
    elif run.status == "awaiting_funding" and workgroup.wallet_balance_kobo >= run.total_kobo:
        run.status = "ready"
        run.funded_at = utcnow()
    audit(session, action="payroll.item_removed", summary=f"Removed {target.staff_name} from payroll {run.number}", actor=actor, workgroup_id=workgroup.id)
    return run


async def funding_options(session: AsyncSession, workgroup: Workgroup, run: PayrollRun) -> dict[str, Any]:
    from .payments import funding_quote

    shortfall = max(0, run.total_kobo - workgroup.wallet_balance_kobo)
    request = _round_up_naira(shortfall, 100) if shortfall else 0
    options: dict[str, Any] = {
        "shortfall_kobo": shortfall,
        "request_kobo": request,
        "wallet_balance_kobo": workgroup.wallet_balance_kobo,
        "total_kobo": run.total_kobo,
        "checkout": await funding_quote(session, request, "checkout") if request else None,
        "transfer": None,
    }
    if request and workgroup.dva_account_number:
        quote = await funding_quote(session, request, "dva")
        options["transfer"] = {
            **quote,
            "account_number": workgroup.dva_account_number,
            "account_name": workgroup.dva_account_name,
            "bank_name": workgroup.dva_bank_name,
        }
    return options


def _round_up_naira(kobo: int, step_naira: int) -> int:
    step = step_naira * 100
    return -(-kobo // step) * step


async def submit(session: AsyncSession, workgroup: Workgroup, run: PayrollRun, actor: User | None) -> PayrollRun:
    if run.status not in EDITABLE_RUN:
        raise Conflict(f"Payroll {run.number} is already {run.status.replace('_', ' ')}.")
    await billing.require_usable(session, workgroup)
    run.submitted_at = run.submitted_at or utcnow()
    if workgroup.wallet_balance_kobo >= run.total_kobo:
        run.status = "ready"
        run.funded_at = run.funded_at or utcnow()
    else:
        run.status = "awaiting_funding"
    audit(
        session,
        action="payroll.submitted",
        summary=f"Payroll {run.number} {'is funded and ready' if run.status == 'ready' else 'is awaiting funding'}",
        actor=actor,
        actor_label=None if actor else "Automatic payday",
        workgroup_id=workgroup.id,
        meta={"run_id": str(run.id)},
    )
    return run


async def start_funding(session: AsyncSession, workgroup: Workgroup, run: PayrollRun, user: User, channel: str) -> Payment:
    from .payments import start_checkout

    if run.status not in ("awaiting_funding", "draft"):
        raise Conflict("This payroll doesn't need funding.")
    if run.status == "draft":
        await submit(session, workgroup, run, user)
        if run.status == "ready":
            raise Conflict("Your wallet already covers this payroll. You can disburse now.", code="already_funded")
    options = await funding_options(session, workgroup, run)
    return await start_checkout(
        session, workgroup=workgroup, user=user, purpose="payroll", net_kobo=options["request_kobo"], channel=channel, payroll_run=run
    )


async def on_funds_available(session: AsyncSession, workgroup: Workgroup, run_id: uuid.UUID) -> str | None:
    """Called after a wallet credit. Returns 'ready', 'auto' or None."""
    run = await session.get(PayrollRun, run_id)
    if run is None or run.status != "awaiting_funding":
        return None
    if workgroup.wallet_balance_kobo < run.total_kobo:
        return None
    run.status = "ready"
    run.funded_at = utcnow()
    if run.trigger == "automatic":
        return "auto"  # the scheduler disburses ready automatic runs within a minute
    owner = workgroup.owner
    notify(
        session,
        owner.id,
        f"Payroll {run.number} is funded",
        f"Funds confirmed. Disburse to pay {run.staff_count} staff {format_naira(run.salaries_kobo)}.",
        kind="success",
        link=f"/app/payroll/runs/{run.id}",
        workgroup_id=workgroup.id,
    )
    queue_email(
        session,
        owner.email,
        "payroll_funded",
        {
            "name": owner.first_name,
            "company": workgroup.name,
            "run_number": run.number,
            "period": run.period_label,
            "staff_count": run.staff_count,
            "total": run.total_kobo,
            "salaries": run.salaries_kobo,
            "fees": run.transfer_fees_kobo,
            "commission": run.commission_kobo,
            "commission_percent": bps_label(run.commission_bps),
            "link": f"{settings.FRONTEND_URL}/app/payroll/runs/{run.id}",
        },
    )
    return "ready"


async def cancel(session: AsyncSession, workgroup: Workgroup, run: PayrollRun, actor: User) -> PayrollRun:
    if run.status not in EDITABLE_RUN:
        raise Conflict("Only payroll that hasn't been disbursed can be cancelled.")
    run.status = "canceled"
    run.canceled_at = utcnow()
    audit(session, action="payroll.canceled", summary=f"Cancelled payroll {run.number}", actor=actor, workgroup_id=workgroup.id)
    return run


# ---------------------------------------------------------------- disburse
async def disburse(session: AsyncSession, workgroup_id: uuid.UUID, run_id: uuid.UUID, actor: User | None) -> PayrollRun:
    """Debits the wallet and sends every transfer. Safe to call twice."""
    provider = get_provider()
    async with redis_lock(f"disburse:{run_id}", ttl_seconds=600) as acquired:
        if not acquired:
            raise Conflict("This payroll is already being disbursed.", code="disbursement_in_progress")

        # Phase 0: make sure the platform's Paystack balance can cover it.
        preview_run = await get_run(session, workgroup_id, run_id)
        if preview_run.status not in ("ready", "awaiting_funding"):
            raise Conflict(f"Payroll {preview_run.number} is {preview_run.status.replace('_', ' ')} and can't be disbursed.")
        try:
            platform_balance = await provider.get_balance()
        except PaystackError as exc:
            raise ServiceUnavailable("We couldn't reach Paystack to start the transfers. Please try again in a few minutes.") from exc
        needed = preview_run.salaries_kobo + preview_run.transfer_fees_kobo
        if platform_balance < needed:
            await _alert_admin(
                session,
                "Paystack balance too low for a payroll",
                f"Payroll {preview_run.number} needs {format_naira(needed)} in the Paystack balance but only {format_naira(platform_balance)} is available. "
                "Check that collections settle to the Paystack balance.",
            )
            await session.commit()
            raise ServiceUnavailable(
                "Disbursement is temporarily unavailable. Our team has been alerted and your funds are safe in your wallet.", code="platform_balance_low"
            )
        await session.rollback()  # release the read snapshot before locking

        # Phase 1: lock, validate, debit, queue.
        workgroup = await wallet.lock_workgroup(session, workgroup_id)
        run = await get_run(session, workgroup_id, run_id, lock=True)
        if run.status not in ("ready", "awaiting_funding"):
            raise Conflict(f"Payroll {run.number} is {run.status.replace('_', ' ')} and can't be disbursed.")
        await billing.require_usable(session, workgroup)
        items = await load_items(session, run.id)
        valid: list[PayrollItem] = []
        for item in items:
            member = await session.get(StaffMember, item.staff_id) if item.staff_id else None
            if member is None or member.status != "registered" or not member.paystack_recipient_code:
                await session.delete(item)
                continue
            if member.paystack_recipient_code != item.recipient_code:
                # Bank details changed after the payroll was prepared: pay the new account.
                item.recipient_code = member.paystack_recipient_code
                item.account_number = member.account_number
                item.account_name = member.account_name
                item.bank_name = member.bank_name
            valid.append(item)
        _recompute(run, valid)
        if not valid:
            run.status = "canceled"
            run.canceled_at = utcnow()
            run.failure_reason = "No staff left to pay"
            await session.commit()
            raise ValidationFailed("None of the staff in this payroll can be paid any more.")
        if workgroup.wallet_balance_kobo < run.total_kobo:
            run.status = "awaiting_funding"
            await session.commit()
            raise InsufficientFunds(
                f"Your wallet has {format_naira(workgroup.wallet_balance_kobo)} but this payroll needs {format_naira(run.total_kobo)}.",
                details={"shortfall_kobo": run.total_kobo - workgroup.wallet_balance_kobo, "run_id": str(run.id)},
            )
        meta = {"run_id": str(run.id), "staff": run.staff_count}
        await wallet.debit(session, workgroup, run.salaries_kobo, "payroll", f"Payroll {run.number} · {run.staff_count} staff · {run.period_label}",
                           reference=f"run:{run.id}:salaries", payroll_run_id=run.id, meta=meta)
        if run.transfer_fees_kobo:
            await wallet.debit(session, workgroup, run.transfer_fees_kobo, "transfer_fees", f"Paystack transfer fees · payroll {run.number}",
                               reference=f"run:{run.id}:fees", payroll_run_id=run.id, meta=meta)
        if run.commission_kobo:
            await wallet.debit(session, workgroup, run.commission_kobo, "commission",
                               f"{settings.APP_NAME} service fee ({bps_label(run.commission_bps)}) · payroll {run.number}",
                               reference=f"run:{run.id}:commission", payroll_run_id=run.id, meta=meta)
        for item in valid:
            item.status = "queued"
        run.status = "processing"
        run.funded_at = run.funded_at or utcnow()
        run.disbursed_at = utcnow()
        run.disbursed_by_id = actor.id if actor else None
        audit(
            session,
            action="payroll.disbursed",
            summary=f"Disbursed payroll {run.number}: {format_naira(run.salaries_kobo)} to {run.staff_count} staff",
            actor=actor,
            actor_label=None if actor else "Automatic payday",
            workgroup_id=workgroup.id,
            meta={"run_id": str(run.id), "total_kobo": run.total_kobo},
        )
        await session.commit()

        # Phase 2: send transfers in batches.
        await send_queued(session, run.id)
        return await get_run(session, workgroup_id, run_id)


async def send_queued(session: AsyncSession, run_id: uuid.UUID) -> None:
    provider = get_provider()
    queued = list(
        (await session.execute(select(PayrollItem).where(PayrollItem.run_id == run_id, PayrollItem.status == "queued"))).scalars().all()
    )
    run = await session.get(PayrollRun, run_id)
    for start in range(0, len(queued), BATCH_SIZE):
        batch = queued[start : start + BATCH_SIZE]
        payload = [
            {"amount": i.amount_kobo, "recipient": i.recipient_code, "reference": i.reference,
             "reason": f"{run.period_label} salary"[:100]}
            for i in batch
        ]
        try:
            results = await provider.bulk_transfer(payload)
        except PaystackError as exc:
            if exc.transient:
                # Paystack may or may not have accepted them: let the reconciler verify.
                for item in batch:
                    item.status = "processing"
                    item.needs_verification = True
                await session.commit()
                continue
            logger.error("Bulk transfer rejected for run %s: %s", run_id, exc.message)
            await session.commit()
            for item in batch:
                await apply_transfer_update(session, item.reference, "failed", f"Transfer rejected: {exc.message}"[:255], None)
            await _alert_admin(session, "Bulk transfer rejected by Paystack", f"Run {run.number}: {exc.message}")
            await session.commit()
            continue
        by_ref = {r.reference: r for r in results}
        await session.commit()
        for item in batch:
            result = by_ref.get(item.reference)
            if result is None:
                await apply_transfer_update(session, item.reference, "processing", None, None, needs_verification=True)
            else:
                if result.status == "otp":
                    await _alert_admin(session, "Paystack transfers need OTP", "Disable 'Confirm transfers with OTP' in the Paystack dashboard so payroll can run.")
                await apply_transfer_update(session, item.reference, result.status, result.reason, result.transfer_code)
            await session.commit()
    await session.commit()


async def apply_transfer_update(
    session: AsyncSession, reference: str, status: str, reason: str | None, transfer_code: str | None, *, needs_verification: bool = False
) -> PayrollItem | None:
    """Single place where an item's outcome is decided. Idempotent."""
    item = (
        await session.execute(select(PayrollItem).where(PayrollItem.reference == reference).with_for_update().execution_options(populate_existing=True))
    ).scalar_one_or_none()
    if item is None:
        return None
    status = status.lower()
    run = await session.get(PayrollRun, item.run_id, with_for_update=True, populate_existing=True)
    if transfer_code and not item.transfer_code:
        item.transfer_code = transfer_code

    if status == "success":
        if item.status in ("success", "failed", "reversed"):
            return item
        item.status = "success"
        item.paid_at = utcnow()
        item.failure_reason = None
        item.needs_verification = False
        run.paid_kobo += item.amount_kobo
        await _send_payslip(session, run, item)
    elif status in ("failed", "reversed"):
        if item.status in ("failed", "reversed"):
            return item
        if item.status == "success":
            if status != "reversed":
                return item
            run.paid_kobo -= item.amount_kobo
        item.status = status
        item.failure_reason = (reason or ("Transfer reversed by the bank" if status == "reversed" else "Transfer failed"))[:255]
        item.needs_verification = False
        await _refund_item(session, run, item)
    else:
        if item.status in TERMINAL_ITEM:
            return item
        item.status = "processing"
        if needs_verification:
            item.needs_verification = True
    await session.flush()
    await finalize_if_done(session, run)
    return item


async def _refund_item(session: AsyncSession, run: PayrollRun, item: PayrollItem) -> None:
    if item.refunded:
        return
    workgroup = await wallet.lock_workgroup(session, item.workgroup_id)
    amount = item.amount_kobo + item.fee_kobo + item.commission_kobo
    await wallet.credit(
        session,
        workgroup,
        amount,
        "refund",
        f"Refund · {item.staff_name} · payroll {run.number}",
        reference=f"refund:{item.reference}",
        payroll_run_id=run.id,
        meta={"item_id": str(item.id), "salary_kobo": item.amount_kobo, "fee_kobo": item.fee_kobo, "commission_kobo": item.commission_kobo},
    )
    item.refunded = True
    run.refunded_kobo += amount


async def _send_payslip(session: AsyncSession, run: PayrollRun, item: PayrollItem) -> None:
    if item.receipt_sent or not item.staff_email:
        return
    workgroup = await session.get(Workgroup, run.workgroup_id)
    queue_email(
        session,
        item.staff_email,
        "payslip",
        {
            "staff_name": item.staff_name.split(" ")[0],
            "company": workgroup.name,
            "period": run.period_label,
            "amount": item.amount_kobo,
            "staff_code": item.staff_code,
            "account_name": item.account_name,
            "bank_name": item.bank_name or "",
            "account_masked": mask_account(item.account_number),
            "reference": item.reference,
            "paid_at": (item.paid_at or utcnow()).strftime("%d %b %Y, %H:%M UTC"),
        },
    )
    item.receipt_sent = True


async def finalize_if_done(session: AsyncSession, run: PayrollRun) -> None:
    if run.status != "processing":
        return
    counts = Counter(
        (await session.execute(select(PayrollItem.status).where(PayrollItem.run_id == run.id))).scalars().all()
    )
    if any(counts.get(s, 0) for s in OPEN_ITEM):
        return
    success = counts.get("success", 0)
    failed = counts.get("failed", 0) + counts.get("reversed", 0)
    run.status = "completed" if failed == 0 else ("failed" if success == 0 else "partially_failed")
    run.completed_at = utcnow()
    workgroup = await session.get(Workgroup, run.workgroup_id)
    owner = workgroup.owner
    if run.status == "completed":
        title, outcome = f"All {success} staff have been paid", "all staff paid"
    elif run.status == "partially_failed":
        title, outcome = f"{success} paid, {failed} need attention", f"{failed} transfer(s) failed"
    else:
        title, outcome = "The transfers could not be completed", "transfers failed"
    notify(
        session,
        owner.id,
        f"Payroll {run.number}: {outcome}",
        f"{format_naira(run.paid_kobo)} paid to {success} staff." + (f" {format_naira(run.refunded_kobo)} refunded to your wallet." if failed else ""),
        kind="success" if failed == 0 else "warning",
        link=f"/app/payroll/runs/{run.id}",
        workgroup_id=workgroup.id,
    )
    queue_email(
        session,
        owner.email,
        "payroll_completed",
        {
            "name": owner.first_name,
            "company": workgroup.name,
            "run_number": run.number,
            "period": run.period_label,
            "outcome": outcome,
            "outcome_title": title,
            "paid_amount": run.paid_kobo,
            "paid_count": success,
            "staff_count": success + failed,
            "failed_count": failed,
            "refunded": run.refunded_kobo,
            "completed_at": run.completed_at.strftime("%d %b %Y, %H:%M UTC"),
            "link": f"{settings.FRONTEND_URL}/app/payroll/runs/{run.id}",
        },
    )
    audit(session, action="payroll.completed", summary=f"Payroll {run.number} finished: {outcome}", actor_label="Streixpei",
          workgroup_id=workgroup.id, meta={"run_id": str(run.id)})


async def retry_failed(session: AsyncSession, workgroup: Workgroup, run: PayrollRun, actor: User) -> PayrollRun:
    if run.status not in ("partially_failed", "failed"):
        raise Conflict("There are no failed payments to retry in this payroll.")
    failed_staff = (
        await session.execute(
            select(PayrollItem.staff_id).where(PayrollItem.run_id == run.id, PayrollItem.status.in_(["failed", "reversed"]), PayrollItem.staff_id.is_not(None))
        )
    ).scalars().all()
    if not failed_staff:
        raise Conflict("The staff from the failed payments are no longer in this workgroup.")
    new_run = await create_run(session, workgroup, actor, trigger="retry", staff_ids=list(failed_staff),
                               note=f"Retry of failed payments from {run.number}")
    return new_run


async def _alert_admin(session: AsyncSession, title: str, body: str) -> None:
    logger.error("ADMIN ALERT: %s — %s", title, body)
    if settings.ADMIN_EMAIL:
        queue_email(session, settings.ADMIN_EMAIL, "admin_alert", {"title": title, "body": body, "details": None})


# --------------------------------------------------------------- automation
async def run_due_paydays(session: AsyncSession) -> dict[str, int]:
    now = utcnow()
    stats = {"created": 0, "disbursed": 0, "awaiting": 0, "manual_reminders": 0, "skipped": 0}
    due = (
        await session.execute(
            select(Workgroup.id).where(Workgroup.status == "active", Workgroup.next_payday_at.is_not(None), Workgroup.next_payday_at <= now)
        )
    ).scalars().all()
    for workgroup_id in due:
        workgroup = await session.get(Workgroup, workgroup_id)
        payday = workgroup.next_payday_at
        workgroup.next_payday_at = next_payday(workgroup.payday_day, workgroup.payday_time, workgroup.timezone, after=now)
        owner = workgroup.owner
        if workgroup.payment_mode != "automatic":
            notify(session, owner.id, f"It's payday for {workgroup.name}", "Your payroll is set to manual. Review and pay your staff today.",
                   kind="info", link="/app/payroll", workgroup_id=workgroup.id)
            stats["manual_reminders"] += 1
            await session.commit()
            continue
        period_key, _ = period_for(payday, workgroup.timezone)
        exists = (
            await session.execute(
                select(PayrollRun.id).where(PayrollRun.workgroup_id == workgroup.id, PayrollRun.trigger == "automatic",
                                            PayrollRun.period_key == period_key, PayrollRun.status != "canceled")
            )
        ).first()
        if exists:
            stats["skipped"] += 1
            await session.commit()
            continue
        try:
            run = await create_run(session, workgroup, None, trigger="automatic", period_moment=payday)
            await submit(session, workgroup, run, None)
            stats["created"] += 1
        except AppError as exc:
            notify(session, owner.id, f"Automatic payroll couldn't start for {workgroup.name}", exc.message, kind="danger",
                   link="/app/payroll", workgroup_id=workgroup.id)
            await session.commit()
            continue
        if run.status == "awaiting_funding":
            await _notify_shortfall(session, workgroup, run)
            stats["awaiting"] += 1
        await session.commit()
    stats["disbursed"] += await disburse_ready_automatic(session)
    return stats


async def disburse_ready_automatic(session: AsyncSession) -> int:
    ready = (
        await session.execute(select(PayrollRun.id, PayrollRun.workgroup_id).where(PayrollRun.trigger == "automatic", PayrollRun.status == "ready"))
    ).all()
    count = 0
    for run_id, workgroup_id in ready:
        try:
            await disburse(session, workgroup_id, run_id, None)
            count += 1
        except AppError as exc:
            await session.rollback()
            logger.warning("Automatic disbursement of %s deferred: %s", run_id, exc.message)
        except Exception:
            await session.rollback()
            logger.exception("Automatic disbursement of %s failed", run_id)
    return count


async def _notify_shortfall(session: AsyncSession, workgroup: Workgroup, run: PayrollRun) -> None:
    owner = workgroup.owner
    options = await funding_options(session, workgroup, run)
    notify(session, owner.id, f"Fund {workgroup.name} payroll",
           f"Payroll {run.number} needs {format_naira(options['shortfall_kobo'])} more. It will pay out automatically once funded.",
           kind="warning", link=f"/app/payroll/runs/{run.id}", workgroup_id=workgroup.id)
    transfer = options.get("transfer") or {}
    queue_email(
        session,
        owner.email,
        "payroll_shortfall",
        {
            "name": owner.first_name,
            "company": workgroup.name,
            "period": run.period_label,
            "total": run.total_kobo,
            "balance": workgroup.wallet_balance_kobo,
            "shortfall": options["shortfall_kobo"],
            "staff_count": run.staff_count,
            "automatic": run.trigger == "automatic",
            "dva_account_number": transfer.get("account_number"),
            "dva_bank_name": transfer.get("bank_name"),
            "dva_account_name": transfer.get("account_name"),
            "transfer_amount": transfer.get("gross_kobo", 0),
            "link": f"{settings.FRONTEND_URL}/app/payroll/runs/{run.id}",
        },
    )


async def send_payday_reminders(session: AsyncSession) -> int:
    from .workgroups import estimate_payroll, staff_stats

    now = utcnow()
    days = await platform.get_int(session, "payday_reminder_days")
    upcoming = (
        await session.execute(
            select(Workgroup.id).where(Workgroup.status == "active", Workgroup.next_payday_at.is_not(None),
                                       Workgroup.next_payday_at > now, Workgroup.next_payday_at <= now + timedelta(days=days))
        )
    ).scalars().all()
    sent = 0
    for workgroup_id in upcoming:
        workgroup = await session.get(Workgroup, workgroup_id)
        key, _ = period_for(workgroup.next_payday_at, workgroup.timezone)
        if workgroup.last_reminder_key == key:
            continue
        if not await billing.is_usable(session, workgroup.subscription):
            continue
        workgroup.last_reminder_key = key
        stats = await staff_stats(session, workgroup.id)
        estimate = await estimate_payroll(session, workgroup.id)
        if stats["registered"] == 0:
            await session.commit()
            continue
        owner = workgroup.owner
        shortfall = max(0, estimate["total_kobo"] - workgroup.wallet_balance_kobo)
        automatic = workgroup.payment_mode == "automatic"
        delta = workgroup.next_payday_at - now
        when = "tomorrow" if delta <= timedelta(days=1) else f"in {delta.days} days"
        from ..core.timeutil import get_tz

        payday_local = workgroup.next_payday_at.astimezone(get_tz(workgroup.timezone))
        if automatic:
            headline = "Payroll will run automatically" if shortfall == 0 else "Top up before automatic payday"
            status_line = (
                "Your wallet covers the estimated payroll, so salaries will go out automatically."
                if shortfall == 0
                else f"Your wallet is {format_naira(shortfall)} short of the estimated payroll."
            )
        else:
            headline = "Payday is coming up"
            status_line = "Payroll is set to manual — prepare and pay it on the day."
        queue_email(
            session,
            owner.email,
            "payday_reminder",
            {
                "name": owner.first_name,
                "company": workgroup.name,
                "when": when,
                "headline": headline,
                "status_line": status_line,
                "payday_date": payday_local.strftime("%A, %d %B"),
                "mode_label": "Automatic" if automatic else "Manual",
                "estimated_total": estimate["total_kobo"],
                "balance": workgroup.wallet_balance_kobo,
                "ready_count": stats["payout_ready"],
                "staff_count": stats["registered"],
                "needs_funding": shortfall > 0,
                "shortfall": shortfall,
                "not_ready": stats["registered"] - stats["payout_ready"],
                "link": f"{settings.FRONTEND_URL}/app/{'wallet' if shortfall and automatic else 'payroll'}",
                "cta": "Fund wallet" if shortfall and automatic else "Open payroll",
            },
        )
        notify(session, owner.id, f"{workgroup.name} payday {when}", status_line, kind="warning" if shortfall and automatic else "info",
               link="/app/payroll", workgroup_id=workgroup.id)
        sent += 1
        await session.commit()
    await session.commit()
    return sent


async def reconcile_transfers(session: AsyncSession) -> int:
    """Settles transfers whose webhook never arrived."""
    provider = get_provider()
    now = utcnow()
    stale = (
        await session.execute(
            select(PayrollItem.reference, PayrollItem.status, PayrollItem.updated_at).where(
                PayrollItem.status == "processing", PayrollItem.updated_at < now - timedelta(minutes=10)
            ).limit(200)
        )
    ).all()
    settled = 0
    for reference, status, updated_at in stale:
        try:
            result = await provider.verify_transfer(reference)
        except PaystackError:
            continue
        if result is None:
            if updated_at < now - timedelta(minutes=30):
                await apply_transfer_update(session, reference, "failed", "Transfer was not accepted by Paystack", None)
                settled += 1
        elif result.status in ("success", "failed", "reversed"):
            await apply_transfer_update(session, reference, result.status, result.reason, result.transfer_code)
            settled += 1
        else:
            item = (await session.execute(select(PayrollItem).where(PayrollItem.reference == reference))).scalar_one()
            item.updated_at = now  # check again later
        await session.commit()
    # Items still "queued" mean the server stopped between debiting the wallet
    # and sending. Paystack may already have them, so verify before resending
    # (resending an accepted reference would be rejected and wrongly refunded).
    stuck = (
        await session.execute(
            select(PayrollItem.run_id, PayrollItem.reference).where(
                PayrollItem.status == "queued", PayrollItem.updated_at < now - timedelta(minutes=2)
            ).limit(500)
        )
    ).all()
    by_run: dict[uuid.UUID, list[str]] = {}
    for run_id, reference in stuck:
        by_run.setdefault(run_id, []).append(reference)
    for run_id, references in by_run.items():
        async with redis_lock(f"disburse:{run_id}", ttl_seconds=600) as acquired:
            if not acquired:
                continue
            verified_all = True
            for reference in references:
                try:
                    result = await provider.verify_transfer(reference)
                except PaystackError:
                    verified_all = False
                    break
                if result is not None:
                    await apply_transfer_update(session, reference, result.status, result.reason, result.transfer_code)
                    settled += 1
            await session.commit()
            if verified_all:
                await send_queued(session, run_id)
    return settled
