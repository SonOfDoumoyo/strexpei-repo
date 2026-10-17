"""Plans, subscriptions and invoices.

Pricing is per workgroup and depends on how many staff it pays:

    monthly price = plan.base_fee + plan.per_staff x seats

The plan (Small / Medium / Large) is chosen automatically from the seat
count, so bigger organisations get a lower per-staff rate. Annual billing
charges ``12 - annual_discount_months`` months. Adding seats mid-period is
prorated. On top of the subscription, Streixpei earns a commission on every
salary disbursed (see ``FeeSchedule.commission_bps``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import AppError, Conflict, PaymentRequired, ValidationFailed
from ..core.ids import human_number
from ..core.money import bps_label, format_naira
from ..core.timeutil import add_months, utcnow
from ..models import Invoice, Plan, StaffMember, Subscription, User, Workgroup
from . import platform, wallet
from .activity import audit, notify
from .mailer import queue_email

logger = logging.getLogger("streixpei.billing")

DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "code": "small",
        "name": "Small",
        "tagline": "For small teams getting payroll in order",
        "min_staff": 1,
        "max_staff": 25,
        "base_fee_kobo": 5_000_00,
        "per_staff_kobo": 500_00,
        "ai_monthly_quota": 100,
        "sort_order": 1,
        "features": [
            "Up to 25 staff",
            "Staff onboarding link & QR code",
            "Upload or auto-generate staff IDs",
            "Bank account verification",
            "Manual & automatic payday",
            "Permanent funding account number",
            "Email payslips for every staff member",
            "SPI assistant · 100 requests/month",
        ],
    },
    {
        "code": "medium",
        "name": "Medium",
        "tagline": "For growing businesses with structured payroll",
        "min_staff": 26,
        "max_staff": 150,
        "base_fee_kobo": 15_000_00,
        "per_staff_kobo": 400_00,
        "ai_monthly_quota": 500,
        "sort_order": 2,
        "features": [
            "26 – 150 staff",
            "Everything in Small",
            "Lower price per staff member",
            "SPI assistant · 500 requests/month",
        ],
    },
    {
        "code": "large",
        "name": "Large",
        "tagline": "For organisations paying hundreds of people",
        "min_staff": 151,
        "max_staff": None,
        "base_fee_kobo": 50_000_00,
        "per_staff_kobo": 300_00,
        "ai_monthly_quota": 2000,
        "sort_order": 3,
        "features": [
            "151+ staff",
            "Everything in Medium",
            "Lowest per-staff rate",
            "Priority support",
            "SPI assistant · 2,000 requests/month",
        ],
    },
]


# ---------------------------------------------------------------- plans
async def seed_plans(session: AsyncSession) -> None:
    for data in DEFAULT_PLANS:
        if await session.get(Plan, data["code"]) is None:
            session.add(Plan(**data))
    await session.flush()


async def list_plans(session: AsyncSession, include_inactive: bool = False) -> list[Plan]:
    stmt = select(Plan).order_by(Plan.sort_order, Plan.min_staff)
    if not include_inactive:
        stmt = stmt.where(Plan.active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def plan_for_seats(session: AsyncSession, seats: int) -> Plan:
    plans = await list_plans(session)
    if not plans:
        raise AppError("No subscription plans are configured.", status_code=500, code="plans_missing")
    for plan in plans:
        if seats >= plan.min_staff and (plan.max_staff is None or seats <= plan.max_staff):
            return plan
    # Seat count above every max: use the largest plan.
    return max(plans, key=lambda p: (p.max_staff is None, p.max_staff or 0))


def monthly_price(plan: Plan, seats: int) -> int:
    return plan.base_fee_kobo + plan.per_staff_kobo * seats


async def cycle_months(session: AsyncSession, cycle: str) -> tuple[int, int]:
    """(months covered, months charged)."""
    if cycle == "annual":
        discount = await platform.get_int(session, "annual_discount_months")
        return 12, max(1, 12 - discount)
    return 1, 1


async def quote(session: AsyncSession, seats: int, cycle: str = "monthly") -> dict[str, Any]:
    plan = await plan_for_seats(session, seats)
    covered, charged = await cycle_months(session, cycle)
    monthly = monthly_price(plan, seats)
    fees = await platform.get_fees(session)
    return {
        "plan": plan_out(plan),
        "seats": seats,
        "billing_cycle": cycle,
        "monthly_kobo": monthly,
        "amount_kobo": monthly * charged,
        "months_covered": covered,
        "months_charged": charged,
        "per_staff_effective_kobo": round(monthly / seats) if seats else 0,
        "commission_bps": fees.commission_bps,
        "commission_label": bps_label(fees.commission_bps),
    }


def plan_out(plan: Plan) -> dict[str, Any]:
    return {
        "code": plan.code,
        "name": plan.name,
        "tagline": plan.tagline,
        "min_staff": plan.min_staff,
        "max_staff": plan.max_staff,
        "base_fee_kobo": plan.base_fee_kobo,
        "per_staff_kobo": plan.per_staff_kobo,
        "ai_monthly_quota": plan.ai_monthly_quota,
        "features": plan.features,
        "active": plan.active,
        "sort_order": plan.sort_order,
    }


# --------------------------------------------------------- subscriptions
async def create_trial(session: AsyncSession, workgroup: Workgroup) -> Subscription:
    plan = await plan_for_seats(session, workgroup.headcount)
    trial_days = await platform.get_int(session, "trial_days")
    now = utcnow()
    sub = Subscription(
        workgroup_id=workgroup.id,
        plan_code=plan.code,
        seats=workgroup.headcount,
        billing_cycle="monthly",
        status="trialing" if trial_days > 0 else "expired",
        trial_ends_at=now + timedelta(days=trial_days) if trial_days > 0 else now,
    )
    session.add(sub)
    await session.flush()
    workgroup.subscription = sub
    return sub


async def get_subscription(session: AsyncSession, workgroup_id: uuid.UUID) -> Subscription | None:
    return (await session.execute(select(Subscription).where(Subscription.workgroup_id == workgroup_id))).scalar_one_or_none()


async def is_usable(session: AsyncSession, sub: Subscription | None, now: datetime | None = None) -> bool:
    if sub is None:
        return False
    now = now or utcnow()
    if sub.status == "trialing":
        return sub.trial_ends_at is not None and now < sub.trial_ends_at
    if sub.status in ("active", "past_due"):
        grace = await platform.get_int(session, "grace_days")
        return sub.current_period_end is not None and now < sub.current_period_end + timedelta(days=grace)
    return False


async def require_usable(session: AsyncSession, workgroup: Workgroup) -> Subscription:
    sub = workgroup.subscription or await get_subscription(session, workgroup.id)
    if not await is_usable(session, sub):
        raise PaymentRequired(
            "Your subscription for this workgroup has ended. Renew it to continue running payroll.",
            details={"workgroup_id": str(workgroup.id)},
        )
    assert sub is not None
    return sub


async def seats_in_use(session: AsyncSession, workgroup_id: uuid.UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(StaffMember).where(StaffMember.workgroup_id == workgroup_id, StaffMember.status != "inactive")
            )
        ).scalar_one()
    )


async def subscription_out(session: AsyncSession, sub: Subscription | None) -> dict[str, Any] | None:
    if sub is None:
        return None
    plan = sub.plan or await session.get(Plan, sub.plan_code)
    covered, charged = await cycle_months(session, sub.billing_cycle)
    monthly = monthly_price(plan, sub.seats)
    now = utcnow()
    ends_at = sub.trial_ends_at if sub.status == "trialing" else sub.current_period_end
    return {
        "id": str(sub.id),
        "status": sub.status,
        "usable": await is_usable(session, sub, now),
        "plan": plan_out(plan),
        "seats": sub.seats,
        "billing_cycle": sub.billing_cycle,
        "monthly_kobo": monthly,
        "renewal_amount_kobo": monthly * charged,
        "trial_ends_at": sub.trial_ends_at,
        "current_period_start": sub.current_period_start,
        "current_period_end": sub.current_period_end,
        "ends_at": ends_at,
        "days_left": max(0, int((ends_at - now).total_seconds() // 86400)) if ends_at else None,
        "auto_renew": sub.auto_renew,
    }


# --------------------------------------------------------------- invoices
async def _void_pending(session: AsyncSession, workgroup_id: uuid.UUID) -> None:
    pending = (await session.execute(select(Invoice).where(Invoice.workgroup_id == workgroup_id, Invoice.status == "pending"))).scalars().all()
    for invoice in pending:
        invoice.status = "void"


async def create_subscription_invoice(session: AsyncSession, workgroup: Workgroup, seats: int, cycle: str) -> Invoice:
    if cycle not in ("monthly", "annual"):
        raise ValidationFailed("Billing cycle must be monthly or annual.")
    max_seats = await platform.get_int(session, "max_seats_per_workgroup")
    if seats < 1 or seats > max_seats:
        raise ValidationFailed(f"Staff count must be between 1 and {max_seats}.")
    in_use = await seats_in_use(session, workgroup.id)
    if seats < in_use:
        raise Conflict(f"This workgroup already has {in_use} staff IDs. Remove some before choosing {seats} seats.")
    sub = workgroup.subscription or await get_subscription(session, workgroup.id)
    now = utcnow()
    if sub and sub.status == "active" and sub.current_period_end and sub.current_period_end > now + timedelta(days=7):
        raise Conflict("Your subscription is already active. Use 'Change staff count' to add seats.")
    plan = await plan_for_seats(session, seats)
    covered, charged = await cycle_months(session, cycle)
    start = now
    if sub and sub.status == "trialing" and sub.trial_ends_at and sub.trial_ends_at > now:
        start = sub.trial_ends_at  # don't eat unused trial days
    elif sub and sub.status in ("active", "past_due") and sub.current_period_end and sub.current_period_end > now:
        start = sub.current_period_end  # early renewal stacks on the current period
    end = add_months(start, covered)
    await _void_pending(session, workgroup.id)
    invoice = Invoice(
        workgroup_id=workgroup.id,
        number=human_number("INV"),
        kind="subscription" if not sub or sub.status != "active" else "renewal",
        plan_code=plan.code,
        seats=seats,
        billing_cycle=cycle,
        period_start=start,
        period_end=end,
        amount_kobo=monthly_price(plan, seats) * charged,
        description=f"{plan.name} plan · {seats} staff · {'annual' if cycle == 'annual' else 'monthly'}",
    )
    session.add(invoice)
    await session.flush()
    return invoice


async def create_seat_change(session: AsyncSession, workgroup: Workgroup, new_seats: int, actor: User) -> dict[str, Any]:
    """Change the staff count. Returns {'applied': bool, 'invoice': Invoice|None}."""
    max_seats = await platform.get_int(session, "max_seats_per_workgroup")
    if new_seats < 1 or new_seats > max_seats:
        raise ValidationFailed(f"Staff count must be between 1 and {max_seats}.")
    in_use = await seats_in_use(session, workgroup.id)
    if new_seats < in_use:
        raise Conflict(
            f"{in_use} staff IDs already exist in this workgroup. Delete unused IDs first or choose at least {in_use}.",
            details={"in_use": in_use},
        )
    sub = workgroup.subscription or await get_subscription(session, workgroup.id)
    assert sub is not None
    now = utcnow()
    old_seats = sub.seats
    if new_seats == old_seats:
        return {"applied": True, "invoice": None}

    active_period = sub.status in ("active", "past_due") and sub.current_period_end and sub.current_period_end > now
    if new_seats < old_seats or not active_period:
        # Downgrades and changes outside a paid period apply immediately;
        # the price follows at the next renewal.
        await _apply_seats(session, workgroup, sub, new_seats, actor)
        return {"applied": True, "invoice": None}

    # Upgrade during a paid period: charge the prorated difference.
    old_plan = await session.get(Plan, sub.plan_code)
    new_plan = await plan_for_seats(session, new_seats)
    covered, charged = await cycle_months(session, sub.billing_cycle)
    old_total = monthly_price(old_plan, old_seats) * charged
    new_total = monthly_price(new_plan, new_seats) * charged
    period_seconds = (sub.current_period_end - sub.current_period_start).total_seconds() if sub.current_period_start else 30 * 86400
    remaining = max(0.0, (sub.current_period_end - now).total_seconds())
    fraction = Decimal(remaining) / Decimal(period_seconds) if period_seconds else Decimal(0)
    amount = int(((new_total - old_total) * fraction).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if amount <= 0:
        await _apply_seats(session, workgroup, sub, new_seats, actor)
        return {"applied": True, "invoice": None}
    await _void_pending(session, workgroup.id)
    invoice = Invoice(
        workgroup_id=workgroup.id,
        number=human_number("INV"),
        kind="seats",
        plan_code=new_plan.code,
        seats=new_seats,
        previous_seats=old_seats,
        billing_cycle=sub.billing_cycle,
        period_start=now,
        period_end=sub.current_period_end,
        amount_kobo=amount,
        description=f"Add {new_seats - old_seats} staff ({old_seats} → {new_seats}), prorated to period end",
    )
    session.add(invoice)
    await session.flush()
    return {"applied": False, "invoice": invoice}


async def _apply_seats(session: AsyncSession, workgroup: Workgroup, sub: Subscription, seats: int, actor: User | None) -> None:
    plan = await plan_for_seats(session, seats)
    previous = sub.seats
    sub.seats = seats
    sub.plan_code = plan.code
    workgroup.headcount = seats
    audit(
        session,
        action="workgroup.seats_changed",
        summary=f"Staff count changed from {previous} to {seats} ({plan.name} plan)",
        actor=actor,
        workgroup_id=workgroup.id,
        meta={"from": previous, "to": seats, "plan": plan.code},
    )


async def mark_invoice_paid(session: AsyncSession, invoice: Invoice, workgroup: Workgroup, via: str) -> None:
    """Applies the invoice's effect. Idempotent."""
    if invoice.status == "paid":
        return
    if invoice.status == "void":
        logger.warning("Payment received for void invoice %s; applying anyway", invoice.number)
    invoice.status = "paid"
    invoice.paid_via = via
    invoice.paid_at = utcnow()
    sub = workgroup.subscription or await get_subscription(session, workgroup.id)
    assert sub is not None
    plan = await session.get(Plan, invoice.plan_code)
    if invoice.kind == "seats":
        await _apply_seats(session, workgroup, sub, invoice.seats, None)
    else:
        sub.plan_code = invoice.plan_code
        sub.seats = max(invoice.seats, await seats_in_use(session, workgroup.id))
        workgroup.headcount = sub.seats
        sub.billing_cycle = invoice.billing_cycle
        if sub.status == "active" and sub.current_period_end and sub.current_period_end >= invoice.period_start:
            sub.current_period_end = invoice.period_end
        else:
            sub.current_period_start = invoice.period_start
            sub.current_period_end = invoice.period_end
        sub.status = "active"
        sub.last_notice_key = None
    owner = workgroup.owner
    audit(
        session,
        action="billing.invoice_paid",
        summary=f"Invoice {invoice.number} paid ({format_naira(invoice.amount_kobo)}) via {via}",
        actor_label=owner.full_name if owner else "Billing",
        actor=owner,
        workgroup_id=workgroup.id,
        meta={"invoice": invoice.number, "amount_kobo": invoice.amount_kobo},
    )
    if owner:
        notify(
            session,
            owner.id,
            "Subscription payment received",
            f"Invoice {invoice.number} for {workgroup.name} was paid. Thank you!",
            kind="success",
            link="/app/billing",
            workgroup_id=workgroup.id,
        )
        queue_email(
            session,
            owner.email,
            "invoice_paid",
            {
                "name": owner.first_name,
                "company": workgroup.name,
                "invoice_number": invoice.number,
                "amount": invoice.amount_kobo,
                "plan_name": plan.name if plan else invoice.plan_code.title(),
                "seats": invoice.seats,
                "cycle_label": "Annual" if invoice.billing_cycle == "annual" else "Monthly",
                "period": f"{invoice.period_start:%d %b %Y} – {invoice.period_end:%d %b %Y}",
                "paid_via": "Workgroup wallet" if via == "wallet" else "Paystack checkout",
                "paid_at": invoice.paid_at.strftime("%d %b %Y"),
                "link": f"{settings.FRONTEND_URL}/app/billing",
            },
        )


async def pay_invoice_from_wallet(session: AsyncSession, invoice: Invoice, workgroup_id: uuid.UUID) -> None:
    workgroup = await wallet.lock_workgroup(session, workgroup_id)
    if invoice.status != "pending":
        raise Conflict("This invoice is no longer payable.")
    await wallet.debit(
        session,
        workgroup,
        invoice.amount_kobo,
        "subscription",
        f"Subscription · invoice {invoice.number}",
        reference=f"invoice:{invoice.number}",
        meta={"invoice_id": str(invoice.id)},
    )
    await mark_invoice_paid(session, invoice, workgroup, "wallet")


# ------------------------------------------------------------ scheduled
async def process_subscriptions(session: AsyncSession) -> dict[str, int]:
    """Trial reminders/expiry, renewals from wallet, past-due handling."""
    now = utcnow()
    grace = await platform.get_int(session, "grace_days")
    stats = {"renewed": 0, "past_due": 0, "expired": 0, "reminded": 0}
    subs = (await session.execute(select(Subscription).where(Subscription.status.in_(["trialing", "active", "past_due"])))).scalars().all()
    for sub in subs:
        workgroup = await session.get(Workgroup, sub.workgroup_id)
        if workgroup is None or workgroup.status != "active":
            continue
        owner = workgroup.owner
        link = f"{settings.FRONTEND_URL}/app/billing"
        renewal = monthly_price(sub.plan or await session.get(Plan, sub.plan_code), sub.seats) * (await cycle_months(session, sub.billing_cycle))[1]

        def send(key: str, headline: str, body: str, *, note: str | None = None, tone: str = "warning", amount: int | None = None, cta: str = "Manage billing") -> None:
            if sub.last_notice_key == key or owner is None:
                return
            sub.last_notice_key = key
            stats["reminded"] += 1
            notify(session, owner.id, headline, body, kind="warning" if tone != "success" else "success", link="/app/billing", workgroup_id=workgroup.id)
            queue_email(
                session,
                owner.email,
                "subscription_notice",
                {"name": owner.first_name, "company": workgroup.name, "headline": headline, "body": body, "note": note,
                 "tone": tone, "amount": amount, "link": link, "cta": cta},
            )

        if sub.status == "trialing" and sub.trial_ends_at:
            if now >= sub.trial_ends_at:
                sub.status = "expired"
                stats["expired"] += 1
                send(
                    f"trial-ended-{sub.trial_ends_at:%Y%m%d}",
                    f"Your {workgroup.name} trial has ended",
                    "your free trial is over. Subscribe to keep onboarding staff and running payroll — your data is safe and waiting.",
                    amount=renewal,
                    cta="Choose a plan",
                )
            elif sub.trial_ends_at - now <= timedelta(days=3):
                send(
                    f"trial-ending-{sub.trial_ends_at:%Y%m%d}",
                    f"{workgroup.name}: trial ends {sub.trial_ends_at:%d %b}",
                    f"your free trial ends on {sub.trial_ends_at:%d %B %Y}. Subscribe now so payroll keeps running without interruption.",
                    amount=renewal,
                    tone="neutral",
                    cta="Subscribe now",
                )
            continue

        if sub.current_period_end is None:
            continue

        if sub.status == "active" and now >= sub.current_period_end:
            if sub.auto_renew:
                try:
                    async with session.begin_nested():
                        invoice = Invoice(
                            workgroup_id=workgroup.id,
                            number=human_number("INV"),
                            kind="renewal",
                            plan_code=(await plan_for_seats(session, sub.seats)).code,
                            seats=sub.seats,
                            billing_cycle=sub.billing_cycle,
                            period_start=sub.current_period_end,
                            period_end=add_months(sub.current_period_end, (await cycle_months(session, sub.billing_cycle))[0]),
                            amount_kobo=renewal,
                            description=f"Automatic renewal · {sub.seats} staff",
                        )
                        session.add(invoice)
                        await session.flush()
                        await pay_invoice_from_wallet(session, invoice, workgroup.id)
                    stats["renewed"] += 1
                    continue
                except AppError:
                    pass  # not enough in the wallet; fall through to past_due
            sub.status = "past_due"
            stats["past_due"] += 1
            send(
                f"past-due-{sub.current_period_end:%Y%m%d}",
                f"Payment needed for {workgroup.name}",
                "we couldn't renew your subscription" + (" from your wallet" if sub.auto_renew else "") +
                f". You have {grace} days to pay before payroll is paused.",
                amount=renewal,
                cta="Pay now",
            )
        elif sub.status == "past_due" and now >= sub.current_period_end + timedelta(days=grace):
            sub.status = "expired"
            stats["expired"] += 1
            send(
                f"expired-{sub.current_period_end:%Y%m%d}",
                f"{workgroup.name} subscription has expired",
                "your subscription has expired, so payroll and staff onboarding are paused. Renew to pick up where you left off.",
                tone="danger",
                amount=renewal,
                cta="Renew subscription",
            )
        elif sub.status == "active" and sub.current_period_end - now <= timedelta(days=3):
            note = None
            if sub.auto_renew and workgroup.wallet_balance_kobo < renewal:
                note = f"Your wallet has {format_naira(workgroup.wallet_balance_kobo)} — top up before renewal or pay by card."
            send(
                f"renewal-soon-{sub.current_period_end:%Y%m%d}",
                f"{workgroup.name} renews on {sub.current_period_end:%d %b}",
                "your subscription renews soon" + (" from your workgroup wallet." if sub.auto_renew else ". Pay before it ends to avoid interruption."),
                note=note,
                tone="neutral",
                amount=renewal,
            )
    await session.commit()
    return stats


def _ensure(cond: bool, message: str) -> None:
    if not cond:
        raise ValidationFailed(message)
