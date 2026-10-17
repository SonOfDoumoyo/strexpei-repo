from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Any, Literal

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import func, select

from ...core.errors import AppError, Conflict, NotFound, Unauthorized, ValidationFailed
from ...core.redis import hit_rate_limit
from ...core.security import verify_password
from ...core.timeutil import utcnow
from ...models import Invoice, Payment, PayrollRun, WalletEntry
from ...schemas.requests import BankIn, FundIn, FundRunIn, PasswordIn, PayInvoiceIn, RunCreateIn, SeatsIn, SubscribeIn, WithdrawIn
from ...services import billing, payments, payroll, withdrawals
from ...services.staff import to_csv
from ..deps import Manager, OwnedWorkgroup, SessionDep, client_ip

router = APIRouter(tags=["money"])
WG = "/workgroups/{workgroup_id}"


# ------------------------------------------------------------------- wallet
def _entry_out(e: WalletEntry) -> dict[str, Any]:
    return {"id": str(e.id), "type": e.entry_type, "direction": e.direction, "amount_kobo": e.amount_kobo, "balance_after_kobo": e.balance_after_kobo,
            "reference": e.reference, "description": e.description, "payroll_run_id": str(e.payroll_run_id) if e.payroll_run_id else None,
            "meta": e.meta, "created_at": e.created_at}


def _range(stmt, column, date_from: date | None, date_to: date | None):
    if date_from:
        stmt = stmt.where(column >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        stmt = stmt.where(column <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
    return stmt


@router.get(WG + "/wallet")
async def wallet(workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    from ...core.config import settings
    from ...services.workgroups import estimate_payroll

    estimate = await estimate_payroll(session, workgroup.id)
    totals = (
        await session.execute(
            select(WalletEntry.entry_type, func.sum(WalletEntry.amount_kobo)).where(WalletEntry.workgroup_id == workgroup.id).group_by(WalletEntry.entry_type)
        )
    ).all()
    return {
        "balance_kobo": workgroup.wallet_balance_kobo,
        "dva": {"account_number": workgroup.dva_account_number, "account_name": workgroup.dva_account_name, "bank_name": workgroup.dva_bank_name}
        if workgroup.dva_account_number else None,
        "dva_available": bool(workgroup.dva_account_number) or settings.PAYSTACK_DVA_ENABLED or settings.PAYMENTS_PROVIDER == "fake",
        "estimated_payroll_kobo": estimate["total_kobo"],
        "shortfall_kobo": max(0, estimate["total_kobo"] - workgroup.wallet_balance_kobo),
        "totals": {t: int(v) for t, v in totals},
        "payment_mode": workgroup.payment_mode,
        "next_payday_at": workgroup.next_payday_at,
    }


@router.get(WG + "/wallet/quote")
async def funding_quote(workgroup: OwnedWorkgroup, session: SessionDep, amount_kobo: int = Query(..., ge=100, le=500_000_000_00),
                        channel: Literal["checkout", "transfer", "dva"] = "checkout") -> dict[str, int]:
    return await payments.funding_quote(session, amount_kobo, channel)


@router.post(WG + "/wallet/dva")
async def create_dva(workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    await payments.ensure_dva(session, workgroup)
    await session.commit()
    return {"account_number": workgroup.dva_account_number, "account_name": workgroup.dva_account_name, "bank_name": workgroup.dva_bank_name}


@router.post(WG + "/wallet/fund", status_code=status.HTTP_201_CREATED)
async def fund_wallet(body: FundIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("fund", str(workgroup.id), 30, 3600)
    payment = await payments.start_checkout(session, workgroup=workgroup, user=user, purpose="wallet", net_kobo=body.amount_kobo, channel=body.channel)
    await session.commit()
    return payments.payment_out(payment)


@router.get(WG + "/wallet/entries")
async def wallet_entries(workgroup: OwnedWorkgroup, session: SessionDep, type: str | None = None, direction: Literal["credit", "debit"] | None = None,
                         date_from: date | None = None, date_to: date | None = None, page: int = Query(1, ge=1),
                         page_size: int = Query(30, ge=1, le=200)) -> dict[str, Any]:
    stmt = select(WalletEntry).where(WalletEntry.workgroup_id == workgroup.id)
    if type:
        stmt = stmt.where(WalletEntry.entry_type == type)
    if direction:
        stmt = stmt.where(WalletEntry.direction == direction)
    stmt = _range(stmt, WalletEntry.created_at, date_from, date_to)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(WalletEntry.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [_entry_out(e) for e in rows], "total": total, "page": page, "page_size": page_size}


@router.get(WG + "/wallet/entries/export")
async def export_entries(workgroup: OwnedWorkgroup, session: SessionDep, date_from: date | None = None, date_to: date | None = None) -> Response:
    stmt = _range(select(WalletEntry).where(WalletEntry.workgroup_id == workgroup.id), WalletEntry.created_at, date_from, date_to)
    rows = (await session.execute(stmt.order_by(WalletEntry.created_at))).scalars().all()
    header = ["Date (UTC)", "Type", "Direction", "Amount (NGN)", "Balance after (NGN)", "Description", "Reference"]
    data = [[e.created_at.strftime("%Y-%m-%d %H:%M"), e.entry_type, e.direction, f"{e.amount_kobo / 100:.2f}", f"{e.balance_after_kobo / 100:.2f}",
             e.description, e.reference or ""] for e in rows]
    return Response(to_csv(header, data), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="wallet-statement-{utcnow():%Y%m%d}.csv"'})


@router.get(WG + "/wallet/withdrawals")
async def list_withdrawals(workgroup: OwnedWorkgroup, session: SessionDep, page: int = Query(1, ge=1),
                           page_size: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    return await withdrawals.list_for(session, workgroup.id, page, page_size)


@router.get(WG + "/wallet/withdrawals/quote")
async def withdrawal_quote(workgroup: OwnedWorkgroup, session: SessionDep,
                           amount_kobo: int = Query(0, ge=0, le=50_000_000_00)) -> dict[str, Any]:
    return await withdrawals.quote(session, workgroup, amount_kobo)


@router.post(WG + "/wallet/withdrawals/resolve")
async def withdrawal_resolve(body: BankIn, workgroup: OwnedWorkgroup, user: Manager) -> dict[str, str]:
    await hit_rate_limit("withdraw-resolve", str(user.id), 30, 3600)
    return await withdrawals.resolve(body.account_number, body.bank_code)


@router.post(WG + "/wallet/withdrawals", status_code=status.HTTP_201_CREATED)
async def create_withdrawal(body: WithdrawIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("withdraw-password", str(user.id), 10, 900)
    if not await verify_password(body.password, user.password_hash):
        raise Unauthorized("Incorrect password.", code="invalid_password")
    workgroup_id = workgroup.id
    await session.commit()
    w = await withdrawals.create(session, workgroup_id, user, amount_kobo=body.amount_kobo, bank_code=body.bank_code,
                                 account_number=body.account_number)
    return withdrawals.withdrawal_out(w)


@router.get(WG + "/payments")
async def list_payments(workgroup: OwnedWorkgroup, session: SessionDep, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    stmt = select(Payment).where(Payment.workgroup_id == workgroup.id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [payments.payment_out(p) for p in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/payments/{reference}")
async def get_payment(reference: str, user: Manager, session: SessionDep) -> dict[str, Any]:
    payment = await payments.get_payment_for_user(session, user, reference)
    return payments.payment_out(payment)


@router.post("/payments/{reference}/verify")
async def verify_payment(reference: str, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("verify-payment", str(user.id), 60, 600)
    await payments.get_payment_for_user(session, user, reference)
    payment = await payments.verify_and_apply(session, reference)
    await session.commit()
    data = payments.payment_out(payment)
    if payment.payroll_run_id:
        run = await session.get(PayrollRun, payment.payroll_run_id)
        data["payroll_run"] = payroll.run_out(run) if run else None
    return data


# ------------------------------------------------------------------ payroll
@router.get(WG + "/payroll/preview")
async def payroll_preview(workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    return await payroll.preview(session, workgroup)


@router.get(WG + "/payroll/runs")
async def list_runs(workgroup: OwnedWorkgroup, session: SessionDep, status_: str | None = Query(None, alias="status"),
                    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    stmt = select(PayrollRun).where(PayrollRun.workgroup_id == workgroup.id)
    if status_:
        stmt = stmt.where(PayrollRun.status.in_(status_.split(",")))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(PayrollRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [payroll.run_out(r) for r in rows], "total": total, "page": page, "page_size": page_size}


async def _run_detail(session, workgroup, run) -> dict[str, Any]:
    data = payroll.run_out(run, await payroll.load_items(session, run.id))
    if run.status in ("draft", "awaiting_funding", "ready"):
        data["funding"] = await payroll.funding_options(session, workgroup, run)
    pending = (
        await session.execute(select(Payment).where(Payment.payroll_run_id == run.id, Payment.status == "pending").order_by(Payment.created_at.desc()).limit(1))
    ).scalar_one_or_none()
    data["pending_payment"] = payments.payment_out(pending) if pending else None
    data["wallet_balance_kobo"] = workgroup.wallet_balance_kobo
    return data


@router.post(WG + "/payroll/runs", status_code=status.HTTP_201_CREATED)
async def create_run(body: RunCreateIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    run = await payroll.create_run(session, workgroup, user, staff_ids=body.staff_ids, note=body.note)
    await session.commit()
    return await _run_detail(session, workgroup, run)


@router.get(WG + "/payroll/runs/{run_id}")
async def get_run(run_id: uuid.UUID, workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    run = await payroll.get_run(session, workgroup.id, run_id)
    return await _run_detail(session, workgroup, run)


@router.delete(WG + "/payroll/runs/{run_id}/items/{item_id}")
async def remove_item(run_id: uuid.UUID, item_id: uuid.UUID, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    run = await payroll.get_run(session, workgroup.id, run_id, lock=True)
    await payroll.remove_item(session, workgroup, run, item_id, user)
    await session.commit()
    return await _run_detail(session, workgroup, run)


@router.post(WG + "/payroll/runs/{run_id}/submit")
async def submit_run(run_id: uuid.UUID, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    run = await payroll.get_run(session, workgroup.id, run_id, lock=True)
    await payroll.submit(session, workgroup, run, user)
    await session.commit()
    return await _run_detail(session, workgroup, run)


@router.post(WG + "/payroll/runs/{run_id}/fund", status_code=status.HTTP_201_CREATED)
async def fund_run(run_id: uuid.UUID, body: FundRunIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("fund", str(workgroup.id), 30, 3600)
    run = await payroll.get_run(session, workgroup.id, run_id, lock=True)
    payment = await payroll.start_funding(session, workgroup, run, user, body.channel)
    await session.commit()
    return payments.payment_out(payment)


@router.post(WG + "/payroll/runs/{run_id}/disburse")
async def disburse_run(run_id: uuid.UUID, body: PasswordIn, request: Request, workgroup: OwnedWorkgroup, user: Manager,
                       session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("disburse-password", str(user.id), 10, 900)
    if not await verify_password(body.password, user.password_hash):
        raise Unauthorized("Incorrect password.", code="invalid_password")
    workgroup_id = workgroup.id
    await session.commit()
    try:
        run = await payroll.disburse(session, workgroup_id, run_id, user)
    except AppError:
        await session.commit()
        raise
    await session.commit()
    workgroup = await session.get(type(workgroup), workgroup_id, populate_existing=True)
    return await _run_detail(session, workgroup, run)


@router.post(WG + "/payroll/runs/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    run = await payroll.get_run(session, workgroup.id, run_id, lock=True)
    await payroll.cancel(session, workgroup, run, user)
    await session.commit()
    return await _run_detail(session, workgroup, run)


@router.post(WG + "/payroll/runs/{run_id}/retry", status_code=status.HTTP_201_CREATED)
async def retry_run(run_id: uuid.UUID, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    run = await payroll.get_run(session, workgroup.id, run_id)
    new_run = await payroll.retry_failed(session, workgroup, run, user)
    await session.commit()
    return await _run_detail(session, workgroup, new_run)


@router.get(WG + "/payroll/runs/{run_id}/export")
async def export_run(run_id: uuid.UUID, workgroup: OwnedWorkgroup, session: SessionDep) -> Response:
    run = await payroll.get_run(session, workgroup.id, run_id)
    items = await payroll.load_items(session, run.id)
    header = ["Staff ID", "Name", "Role", "Bank", "Account", "Account name", "Salary (NGN)", "Transfer fee (NGN)", "Service fee (NGN)",
              "Status", "Reference", "Paid at (UTC)", "Failure reason"]
    rows = [[i.staff_code, i.staff_name, i.role_name or "", i.bank_name or "", i.account_number, i.account_name or "", f"{i.amount_kobo / 100:.2f}",
             f"{i.fee_kobo / 100:.2f}", f"{i.commission_kobo / 100:.2f}", i.status, i.reference,
             i.paid_at.strftime("%Y-%m-%d %H:%M") if i.paid_at else "", i.failure_reason or ""] for i in items]
    return Response(to_csv(header, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{run.number.lower()}.csv"'})


# ------------------------------------------------------------------ billing
def _invoice_out(i: Invoice) -> dict[str, Any]:
    return {"id": str(i.id), "number": i.number, "kind": i.kind, "plan_code": i.plan_code, "seats": i.seats, "previous_seats": i.previous_seats,
            "billing_cycle": i.billing_cycle, "period_start": i.period_start, "period_end": i.period_end, "amount_kobo": i.amount_kobo,
            "status": i.status, "paid_via": i.paid_via, "paid_at": i.paid_at, "description": i.description, "created_at": i.created_at}


@router.get("/plans")
async def plans(session: SessionDep) -> list[dict[str, Any]]:
    return [billing.plan_out(p) for p in await billing.list_plans(session)]


@router.get("/pricing/quote")
async def pricing_quote(session: SessionDep, seats: int = Query(..., ge=1, le=100_000), cycle: Literal["monthly", "annual"] = "monthly") -> dict[str, Any]:
    return await billing.quote(session, seats, cycle)


@router.get(WG + "/billing")
async def billing_overview(workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    invoices = (
        await session.execute(select(Invoice).where(Invoice.workgroup_id == workgroup.id).order_by(Invoice.created_at.desc()).limit(50))
    ).scalars().all()
    sub = workgroup.subscription
    return {
        "subscription": await billing.subscription_out(session, sub),
        "seats_in_use": await billing.seats_in_use(session, workgroup.id),
        "quote_monthly": await billing.quote(session, sub.seats if sub else workgroup.headcount, "monthly"),
        "quote_annual": await billing.quote(session, sub.seats if sub else workgroup.headcount, "annual"),
        "invoices": [_invoice_out(i) for i in invoices],
        "wallet_balance_kobo": workgroup.wallet_balance_kobo,
        "plans": [billing.plan_out(p) for p in await billing.list_plans(session)],
    }


async def _pay_invoice(session, workgroup, user, invoice: Invoice, pay_with: str) -> dict[str, Any]:
    if pay_with == "wallet":
        await billing.pay_invoice_from_wallet(session, invoice, workgroup.id)
        await session.commit()
        return {"invoice": _invoice_out(invoice), "payment": None, "paid": True}
    payment = await payments.start_checkout(session, workgroup=workgroup, user=user, purpose="invoice", net_kobo=invoice.amount_kobo,
                                            channel="checkout", invoice=invoice)
    await session.commit()
    return {"invoice": _invoice_out(invoice), "payment": payments.payment_out(payment), "paid": False}


@router.post(WG + "/billing/subscribe")
async def subscribe(body: SubscribeIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    invoice = await billing.create_subscription_invoice(session, workgroup, body.seats, body.billing_cycle)
    return await _pay_invoice(session, workgroup, user, invoice, body.pay_with)


@router.post(WG + "/billing/seats")
async def change_seats(body: SeatsIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    result = await billing.create_seat_change(session, workgroup, body.seats, user)
    await session.commit()
    invoice = result["invoice"]
    return {"applied": result["applied"], "invoice": _invoice_out(invoice) if invoice else None,
            "subscription": await billing.subscription_out(session, workgroup.subscription)}


@router.post(WG + "/billing/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: uuid.UUID, body: PayInvoiceIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None or invoice.workgroup_id != workgroup.id:
        raise NotFound("Invoice not found.")
    if invoice.status != "pending":
        raise Conflict("This invoice is no longer payable.")
    return await _pay_invoice(session, workgroup, user, invoice, body.pay_with)
