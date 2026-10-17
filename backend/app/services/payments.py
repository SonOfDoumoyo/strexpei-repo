"""Money in: wallet top-ups, payroll funding and subscription checkout.

Two ways to pay, both through Paystack:

* ``checkout`` – Paystack's hosted page (card, bank transfer, USSD, bank).
* ``transfer`` – a bank account number. With a dedicated virtual account
  (DVA) the workgroup gets a permanent account number; without one, the
  checkout opens directly on Paystack's "Pay with Transfer" option which
  shows a one-time account number.

Paystack's processing fee is added on top so the full intended amount lands
in the wallet. The wallet is credited with exactly what Paystack settles
(amount minus the fee Paystack reports).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import AppError, Conflict, NotFound, ProviderError, ServiceUnavailable, ValidationFailed
from ..core.ids import payment_reference
from ..core.money import format_naira
from ..core.timeutil import utcnow
from ..models import Invoice, Payment, PayrollRun, User, Workgroup
from . import billing, platform, wallet
from .activity import audit, notify
from .mailer import queue_email
from .paystack import PaystackError, get_provider

logger = logging.getLogger("streixpei.payments")

MIN_FUNDING_KOBO = 100_00  # NGN 100
MAX_FUNDING_KOBO = 500_000_000_00  # NGN 500m per checkout


def payment_out(payment: Payment) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "reference": payment.reference,
        "purpose": payment.purpose,
        "channel": payment.channel,
        "status": payment.status,
        "amount_kobo": payment.amount_kobo,
        "expected_net_kobo": payment.expected_net_kobo,
        "fee_estimate_kobo": payment.fee_estimate_kobo,
        "fees_kobo": payment.fees_kobo,
        "net_kobo": payment.net_kobo,
        "authorization_url": payment.authorization_url,
        "payroll_run_id": str(payment.payroll_run_id) if payment.payroll_run_id else None,
        "invoice_id": str(payment.invoice_id) if payment.invoice_id else None,
        "workgroup_id": str(payment.workgroup_id),
        "paid_at": payment.paid_at,
        "created_at": payment.created_at,
    }


async def funding_quote(session: AsyncSession, net_kobo: int, channel: str) -> dict[str, int]:
    fees = await platform.get_fees(session)
    fee_channel = "dva" if channel == "dva" else "checkout"
    gross = fees.gross_up(net_kobo, fee_channel)
    return {"net_kobo": net_kobo, "gross_kobo": gross, "fee_kobo": gross - net_kobo}


async def ensure_dva(session: AsyncSession, workgroup: Workgroup) -> Workgroup:
    """Creates a permanent funding account number for the workgroup."""
    if workgroup.dva_account_number:
        return workgroup
    if not settings.PAYSTACK_DVA_ENABLED and settings.PAYMENTS_PROVIDER != "fake":
        raise ServiceUnavailable("Dedicated account numbers aren't enabled yet. Use 'Pay with transfer' at checkout instead.", code="dva_disabled")
    owner = workgroup.owner
    provider = get_provider()
    try:
        if not workgroup.paystack_customer_code:
            local, _, domain = owner.email.partition("@")
            email = f"{local}+wg{workgroup.id.hex[:10]}@{domain}"
            workgroup.paystack_customer_code = await provider.create_customer(
                email=email, first_name=owner.first_name, last_name=f"{owner.last_name} ({workgroup.name})"[:60], phone=owner.phone
            )
            await session.flush()
        account = await provider.create_dedicated_account(workgroup.paystack_customer_code)
    except PaystackError as exc:
        logger.warning("DVA creation failed for %s: %s", workgroup.id, exc.message)
        raise ProviderError("We couldn't create an account number right now. Use 'Pay with transfer' at checkout instead.", code="dva_failed")
    workgroup.dva_account_number = account["account_number"]
    workgroup.dva_account_name = account.get("account_name")
    workgroup.dva_bank_name = account.get("bank_name")
    audit(session, action="wallet.dva_created", summary=f"Created funding account {workgroup.dva_bank_name} {workgroup.dva_account_number}", actor=owner, workgroup_id=workgroup.id)
    return workgroup


async def start_checkout(
    session: AsyncSession,
    *,
    workgroup: Workgroup,
    user: User,
    purpose: str,
    net_kobo: int,
    channel: str,
    payroll_run: PayrollRun | None = None,
    invoice: Invoice | None = None,
) -> Payment:
    if channel not in ("checkout", "transfer"):
        raise ValidationFailed("Choose card/checkout or bank transfer.")
    if net_kobo < MIN_FUNDING_KOBO:
        raise ValidationFailed(f"The minimum payment is {format_naira(MIN_FUNDING_KOBO)}.")
    if net_kobo > MAX_FUNDING_KOBO:
        raise ValidationFailed(f"The maximum single payment is {format_naira(MAX_FUNDING_KOBO)}. Split it into smaller payments.")
    quote = await funding_quote(session, net_kobo, "checkout")
    reference = payment_reference({"wallet": "w", "payroll": "p", "invoice": "i"}[purpose])
    payment = Payment(
        workgroup_id=workgroup.id,
        user_id=user.id,
        purpose=purpose,
        channel=channel,
        reference=reference,
        amount_kobo=quote["gross_kobo"],
        expected_net_kobo=net_kobo,
        fee_estimate_kobo=quote["fee_kobo"],
        payroll_run_id=payroll_run.id if payroll_run else None,
        invoice_id=invoice.id if invoice else None,
    )
    callback = f"{settings.FRONTEND_URL}/app/payments/callback?reference={reference}"
    try:
        result = await get_provider().initialize_transaction(
            email=user.email,
            amount_kobo=payment.amount_kobo,
            reference=reference,
            callback_url=callback,
            metadata={
                "workgroup_id": str(workgroup.id),
                "purpose": purpose,
                "payroll_run_id": str(payroll_run.id) if payroll_run else None,
                "invoice_id": str(invoice.id) if invoice else None,
                "custom_fields": [
                    {"display_name": "Workgroup", "variable_name": "workgroup", "value": workgroup.name},
                    {"display_name": "Purpose", "variable_name": "purpose", "value": purpose},
                ],
            },
            channels=["bank_transfer"] if channel == "transfer" else ["card", "bank", "bank_transfer", "ussd"],
        )
    except PaystackError as exc:
        logger.warning("Checkout initialisation failed: %s", exc.message)
        raise ProviderError("We couldn't start the payment with Paystack. Please try again.")
    payment.authorization_url = result["authorization_url"]
    payment.access_code = result.get("access_code")
    session.add(payment)
    await session.flush()
    return payment


async def get_payment_for_user(session: AsyncSession, user: User, reference: str) -> Payment:
    payment = (await session.execute(select(Payment).where(Payment.reference == reference))).scalar_one_or_none()
    if payment is None:
        raise NotFound("Payment not found.")
    workgroup = await session.get(Workgroup, payment.workgroup_id)
    if workgroup is None or workgroup.owner_id != user.id:
        raise NotFound("Payment not found.")
    return payment


async def verify_and_apply(session: AsyncSession, reference: str) -> Payment:
    """Asks Paystack for the truth about a checkout and applies it (idempotent)."""
    payment = (await session.execute(select(Payment).where(Payment.reference == reference).with_for_update())).scalar_one_or_none()
    if payment is None:
        raise NotFound("Payment not found.")
    if payment.status in ("success", "failed"):
        return payment
    try:
        data = await get_provider().verify_transaction(reference)
    except PaystackError as exc:
        if exc.transient:
            raise ProviderError("Paystack is not responding. We'll keep checking automatically.")
        data = None
    if not data:
        return payment
    status = str(data.get("status", "")).lower()
    if status == "success":
        await apply_successful_charge(session, payment, data)
    elif status in ("failed", "reversed"):
        payment.status = "failed"
        payment.raw = _trim(data)
    return payment


def _trim(data: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "reference", "status", "amount", "fees", "channel", "paid_at", "gateway_response", "currency")
    return {key: data.get(key) for key in keep if key in data}


async def apply_successful_charge(session: AsyncSession, payment: Payment, data: dict[str, Any]) -> None:
    if payment.status == "success":
        return
    amount = int(data.get("amount") or payment.amount_kobo)
    if str(data.get("currency", "NGN")).upper() != "NGN":
        raise AppError("Unsupported currency", code="currency_mismatch")
    fees_reported = data.get("fees")
    fees_schedule = await platform.get_fees(session)
    fees_kobo = int(fees_reported) if fees_reported is not None else fees_schedule.checkout_fee(amount)
    net = amount - fees_kobo
    if net <= 0:
        payment.status = "failed"
        return
    payment.status = "success"
    payment.fees_kobo = fees_kobo
    payment.net_kobo = net
    payment.amount_kobo = amount
    payment.provider_channel = data.get("channel")
    payment.paid_at = _parse_dt(data.get("paid_at")) or utcnow()
    payment.raw = _trim(data)

    workgroup = await wallet.lock_workgroup(session, payment.workgroup_id)
    await wallet.credit(
        session,
        workgroup,
        net,
        "funding",
        {"wallet": "Wallet top-up", "payroll": "Payroll funding", "invoice": "Subscription payment"}[payment.purpose]
        + f" via {_channel_label(payment.provider_channel)}",
        reference=payment.reference,
        payment_id=payment.id,
        meta={"gross_kobo": amount, "fees_kobo": fees_kobo},
    )
    await after_wallet_credit(session, workgroup, payment, amount, fees_kobo, net)


def _channel_label(channel: str | None) -> str:
    return {
        "card": "card",
        "bank": "bank",
        "bank_transfer": "bank transfer",
        "dedicated_nuban": "bank transfer",
        "ussd": "USSD",
    }.get(channel or "", channel or "Paystack")


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def after_wallet_credit(session: AsyncSession, workgroup: Workgroup, payment: Payment | None, gross: int, fees_kobo: int, net: int) -> None:
    """Follow-up once money lands: pay the invoice or advance the payroll run."""
    from . import payroll  # local import: payroll depends on payments

    owner = workgroup.owner
    next_step = None
    link = f"{settings.FRONTEND_URL}/app/wallet"
    link_label = "View wallet"

    if payment and payment.purpose == "invoice" and payment.invoice_id:
        invoice = await session.get(Invoice, payment.invoice_id)
        if invoice and invoice.status in ("pending", "void"):
            charge = invoice.amount_kobo
            if workgroup.wallet_balance_kobo < charge and net >= charge * 99 // 100:
                # Paystack's actual fee differed by a few kobo from our estimate;
                # absorb it rather than leave the customer with an unpaid invoice.
                charge = workgroup.wallet_balance_kobo
            if charge > 0 and workgroup.wallet_balance_kobo >= charge:
                await wallet.debit(
                    session,
                    workgroup,
                    charge,
                    "subscription",
                    f"Subscription · invoice {invoice.number}",
                    reference=f"invoice:{invoice.number}",
                    meta={"invoice_id": str(invoice.id), "invoice_amount_kobo": invoice.amount_kobo},
                )
                await billing.mark_invoice_paid(session, invoice, workgroup, "checkout")
                next_step = f"Invoice {invoice.number} has been paid from this payment."
            else:
                next_step = f"The payment was smaller than invoice {invoice.number}. The money is in your wallet — pay the invoice from your wallet once topped up."
            link = f"{settings.FRONTEND_URL}/app/billing"
            link_label = "View billing"

    run_ids: list[uuid.UUID] = []
    if payment and payment.payroll_run_id:
        run_ids.append(payment.payroll_run_id)
    # Any run waiting for money may now be covered (e.g. a DVA transfer).
    waiting = (
        await session.execute(
            select(PayrollRun.id).where(PayrollRun.workgroup_id == workgroup.id, PayrollRun.status == "awaiting_funding").order_by(PayrollRun.created_at)
        )
    ).scalars().all()
    for run_id in waiting:
        if run_id not in run_ids:
            run_ids.append(run_id)
    for run_id in run_ids:
        outcome = await payroll.on_funds_available(session, workgroup, run_id)
        if outcome == "ready":
            run = await session.get(PayrollRun, run_id)
            next_step = f"Payroll {run.number} is now fully funded. Review it and disburse to pay your staff."
            link = f"{settings.FRONTEND_URL}/app/payroll/runs/{run_id}"
            link_label = "Review and disburse"
        elif outcome == "auto":
            run = await session.get(PayrollRun, run_id)
            next_step = f"Payroll {run.number} is funded and is being disbursed automatically."
            link = f"{settings.FRONTEND_URL}/app/payroll/runs/{run_id}"
            link_label = "Track payroll"

    if owner:
        notify(
            session,
            owner.id,
            "Wallet funded",
            f"{format_naira(net)} was added to {workgroup.name}. Balance: {format_naira(workgroup.wallet_balance_kobo)}.",
            kind="success",
            link="/app/wallet",
            workgroup_id=workgroup.id,
        )
        queue_email(
            session,
            owner.email,
            "funding_received",
            {
                "name": owner.first_name,
                "company": workgroup.name,
                "amount": format_naira(net),
                "gross": gross,
                "fees": fees_kobo,
                "net": net,
                "balance": workgroup.wallet_balance_kobo,
                "method": _channel_label(payment.provider_channel if payment else "dedicated_nuban").capitalize(),
                "reference": payment.reference if payment else "—",
                "paid_at": (payment.paid_at if payment else utcnow()).strftime("%d %b %Y, %H:%M UTC"),
                "next_step": next_step,
                "link": link,
                "link_label": link_label,
            },
        )
    audit(
        session,
        action="wallet.funded",
        summary=f"Wallet funded with {format_naira(net)} (paid {format_naira(gross)})",
        actor_label=owner.full_name if owner else "Paystack",
        actor=owner,
        workgroup_id=workgroup.id,
        meta={"reference": payment.reference if payment else None},
    )


async def apply_dva_charge(session: AsyncSession, data: dict[str, Any]) -> bool:
    """A transfer into a workgroup's dedicated account number."""
    customer_code = ((data.get("customer") or {}).get("customer_code")) or ""
    workgroup = (await session.execute(select(Workgroup).where(Workgroup.paystack_customer_code == customer_code))).unique().scalar_one_or_none()
    if workgroup is None:
        logger.warning("DVA charge for unknown customer %s", customer_code)
        return False
    reference = str(data.get("reference"))
    if (await session.execute(select(Payment.id).where(Payment.reference == reference))).first():
        return True
    amount = int(data.get("amount", 0))
    fees_schedule = await platform.get_fees(session)
    fees_kobo = int(data["fees"]) if data.get("fees") is not None else fees_schedule.dva_fee(amount)
    payment = Payment(
        workgroup_id=workgroup.id,
        user_id=workgroup.owner_id,
        purpose="wallet",
        channel="dva",
        reference=reference,
        amount_kobo=amount,
        expected_net_kobo=amount - fees_kobo,
        fee_estimate_kobo=fees_kobo,
        status="pending",
    )
    session.add(payment)
    await session.flush()
    await apply_successful_charge(session, payment, {**data, "fees": fees_kobo, "channel": "dedicated_nuban"})
    return True


async def reconcile_pending(session: AsyncSession) -> int:
    """Re-checks checkouts the webhook may have missed; expires abandoned ones."""
    now = utcnow()
    pending = (
        await session.execute(
            select(Payment.reference, Payment.created_at).where(
                Payment.status == "pending", Payment.channel != "dva", Payment.created_at < now - timedelta(minutes=5)
            ).limit(100)
        )
    ).all()
    updated = 0
    for reference, created_at in pending:
        try:
            payment = await verify_and_apply(session, reference)
            if payment.status == "pending" and created_at < now - timedelta(days=2):
                payment.status = "abandoned"
            await session.commit()
            updated += 1
        except AppError:
            await session.rollback()
        except Exception:
            logger.exception("Reconciling payment %s failed", reference)
            await session.rollback()
    return updated


async def cancel_if_pending(session: AsyncSession, payment: Payment) -> None:
    if payment.status != "pending":
        raise Conflict("Only pending payments can be cancelled.")
    payment.status = "abandoned"
