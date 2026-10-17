"""Development-only endpoints for the simulated payment provider.

Mounted only when PAYMENTS_PROVIDER=fake (never in production). They let
you click through checkout and bank transfers locally without Paystack.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from ...core.errors import NotFound
from ...models import Payment, Workgroup
from ...services import payments, platform
from ...services.paystack import FakePaystack, get_provider
from ..deps import SessionDep

router = APIRouter(prefix="/dev", tags=["dev"])


class DvaTransferIn(BaseModel):
    amount_kobo: int = Field(ge=100, le=10_000_000_000)


@router.get("/checkout/{reference}")
async def checkout_info(reference: str, session: SessionDep) -> dict[str, Any]:
    payment = (await session.execute(select(Payment).where(Payment.reference == reference))).scalar_one_or_none()
    if payment is None:
        raise NotFound("Unknown payment")
    workgroup = await session.get(Workgroup, payment.workgroup_id)
    return {**payments.payment_out(payment), "workgroup": workgroup.name}


@router.post("/checkout/{reference}/complete")
async def complete_checkout(reference: str, session: SessionDep) -> dict[str, Any]:
    provider = get_provider()
    assert isinstance(provider, FakePaystack)
    payment = (await session.execute(select(Payment).where(Payment.reference == reference))).scalar_one_or_none()
    if payment is None:
        raise NotFound("Unknown payment")
    fees = await platform.get_fees(session)
    channel = "bank_transfer" if payment.channel == "transfer" else "card"
    await provider.complete_transaction(reference, fees.checkout_fee(payment.amount_kobo), channel)
    payment = await payments.verify_and_apply(session, reference)
    await session.commit()
    return payments.payment_out(payment)


@router.post("/workgroups/{workgroup_id}/dva-transfer")
async def simulate_dva_transfer(workgroup_id: uuid.UUID, body: DvaTransferIn, session: SessionDep) -> dict[str, Any]:
    workgroup = await session.get(Workgroup, workgroup_id)
    if workgroup is None or not workgroup.paystack_customer_code:
        raise NotFound("Create the funding account first.")
    fees = await platform.get_fees(session)
    data = {
        "id": uuid.uuid4().int % 10**9,
        "reference": f"dva-sim-{uuid.uuid4().hex[:16]}",
        "amount": body.amount_kobo,
        "fees": fees.dva_fee(body.amount_kobo),
        "currency": "NGN",
        "channel": "dedicated_nuban",
        "status": "success",
        "customer": {"customer_code": workgroup.paystack_customer_code},
    }
    await payments.apply_dva_charge(session, data)
    await session.commit()
    return {"ok": True, "credited_kobo": body.amount_kobo - data["fees"]}
