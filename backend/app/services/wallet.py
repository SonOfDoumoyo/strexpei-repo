"""Workgroup wallet: an append-only ledger with a locked running balance.

Every balance change takes ``SELECT ... FOR UPDATE`` on the workgroup row,
so concurrent payroll runs, top-ups and refunds can never overdraw or lose
an update. Entries with a reference are unique per (type, reference), making
credits from webhooks idempotent.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import InsufficientFunds, NotFound
from ..models import WalletEntry, Workgroup


async def lock_workgroup(session: AsyncSession, workgroup_id: uuid.UUID) -> Workgroup:
    workgroup = (
        await session.execute(
            select(Workgroup).where(Workgroup.id == workgroup_id).with_for_update(of=Workgroup).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if workgroup is None:
        raise NotFound("Workgroup not found.")
    return workgroup


async def entry_exists(session: AsyncSession, entry_type: str, reference: str) -> bool:
    found = await session.execute(
        select(WalletEntry.id).where(WalletEntry.entry_type == entry_type, WalletEntry.reference == reference).limit(1)
    )
    return found.scalar_one_or_none() is not None


async def _post(
    session: AsyncSession,
    workgroup: Workgroup,
    *,
    direction: str,
    amount_kobo: int,
    entry_type: str,
    description: str,
    reference: str | None = None,
    payroll_run_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> WalletEntry:
    if amount_kobo <= 0:
        raise ValueError("Ledger amounts must be positive")
    if direction == "debit":
        if workgroup.wallet_balance_kobo < amount_kobo:
            raise InsufficientFunds(
                details={"balance_kobo": workgroup.wallet_balance_kobo, "required_kobo": amount_kobo,
                         "shortfall_kobo": amount_kobo - workgroup.wallet_balance_kobo}
            )
        workgroup.wallet_balance_kobo -= amount_kobo
    else:
        workgroup.wallet_balance_kobo += amount_kobo
    entry = WalletEntry(
        workgroup_id=workgroup.id,
        entry_type=entry_type,
        direction=direction,
        amount_kobo=amount_kobo,
        balance_after_kobo=workgroup.wallet_balance_kobo,
        reference=reference,
        description=description[:255],
        payroll_run_id=payroll_run_id,
        payment_id=payment_id,
        meta=meta or {},
    )
    session.add(entry)
    try:
        await session.flush()
    except IntegrityError:
        # The caller's transaction is now unusable; let it roll back.
        raise
    return entry


async def credit(session: AsyncSession, workgroup: Workgroup, amount_kobo: int, entry_type: str, description: str, **kwargs: Any) -> WalletEntry:
    return await _post(session, workgroup, direction="credit", amount_kobo=amount_kobo, entry_type=entry_type, description=description, **kwargs)


async def debit(session: AsyncSession, workgroup: Workgroup, amount_kobo: int, entry_type: str, description: str, **kwargs: Any) -> WalletEntry:
    return await _post(session, workgroup, direction="debit", amount_kobo=amount_kobo, entry_type=entry_type, description=description, **kwargs)
