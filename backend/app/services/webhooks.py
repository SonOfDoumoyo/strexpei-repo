"""Paystack webhook processing (signature checked by the route)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Payment, WebhookEvent
from . import payments, payroll, withdrawals

logger = logging.getLogger("streixpei.webhooks")


def event_key(payload: dict[str, Any]) -> str:
    event = str(payload.get("event", "unknown"))
    data = payload.get("data") or {}
    ident = data.get("id") or data.get("reference") or data.get("transfer_code") or ""
    return f"{event}:{ident}:{data.get('status', '')}"[:160]


async def handle_paystack(session: AsyncSession, payload: dict[str, Any]) -> str:
    """Processes one event inside the caller's transaction. Returns an outcome label."""
    event = str(payload.get("event", ""))
    data = payload.get("data") or {}
    record = WebhookEvent(provider="paystack", event_key=event_key(payload), event=event[:60], payload=payload)
    try:
        async with session.begin_nested():
            session.add(record)
            await session.flush()
    except IntegrityError:
        return "duplicate"

    if event == "charge.success":
        reference = str(data.get("reference", ""))
        payment = (await session.execute(select(Payment).where(Payment.reference == reference).with_for_update())).scalar_one_or_none()
        if payment is not None:
            await payments.apply_successful_charge(session, payment, data)
            return "charge_applied"
        if data.get("channel") == "dedicated_nuban" or (data.get("authorization") or {}).get("channel") == "dedicated_nuban":
            return "dva_applied" if await payments.apply_dva_charge(session, data) else "dva_unknown_customer"
        logger.info("charge.success for unknown reference %s", reference)
        return "ignored"

    if event in ("transfer.success", "transfer.failed", "transfer.reversed"):
        status = event.split(".", 1)[1]
        reason = None
        if status != "success":
            # data.reason is our own narration ("October salary"), not a failure reason.
            reason = data.get("gateway_response") or (
                "Transfer reversed by the receiving bank" if status == "reversed" else "The receiving bank declined the transfer"
            )
            reason = str(reason)
        reference = str(data.get("reference", ""))
        if withdrawals.is_withdrawal_reference(reference):
            w = await withdrawals.apply_update(session, reference, status, reason, data.get("transfer_code"))
            return "withdrawal_applied" if w else "transfer_unknown"
        item = await payroll.apply_transfer_update(session, reference, status, reason, data.get("transfer_code"))
        return "transfer_applied" if item else "transfer_unknown"

    return "ignored"
