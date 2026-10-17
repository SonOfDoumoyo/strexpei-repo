"""Actions the SPI assistant can take inside Streixpei.

Every tool runs with the signed-in manager's permissions and only touches
the workgroup currently open in the app.

* ``read`` tools run immediately.
* ``safe`` tools change nothing irreversible (e.g. preparing a draft payroll,
  creating a payment link) and also run immediately.
* ``confirm`` tools are proposed to the user as an action card and only run
  after the user presses Confirm (disbursing money also needs the password).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Any, Awaitable, Callable, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.errors import AppError, NotFound, ValidationFailed
from ...core.money import format_naira, naira_to_kobo
from ...models import PayrollItem, PayrollRun, User, WalletEntry, Workgroup
from .. import billing, payroll, roles, staff, workgroups
from ..mailer import queue_email


@dataclass
class ToolContext:
    session: AsyncSession
    user: User
    workgroup: Workgroup | None
    ip: str | None = None


Handler = Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]
Preparer = Callable[[ToolContext, dict[str, Any]], Awaitable[tuple[str, dict[str, Any]]]]


@dataclass
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    kind: Literal["read", "safe", "confirm"]
    handler: Handler
    prepare: Preparer | None = None
    requires_password: bool = False
    needs_workgroup: bool = True

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, kind: Literal["read", "safe", "confirm"] = "read", properties: dict | None = None,
         required: list[str] | None = None, *, requires_password: bool = False, needs_workgroup: bool = True):
    def decorator(fn: Handler) -> Handler:
        REGISTRY[name] = Tool(
            name=name,
            description=description,
            schema={"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False},
            kind=kind,
            handler=fn,
            requires_password=requires_password,
            needs_workgroup=needs_workgroup,
        )
        return fn

    return decorator


def preparer(name: str):
    def decorator(fn: Preparer) -> Preparer:
        REGISTRY[name].prepare = fn
        return fn

    return decorator


def _wg(ctx: ToolContext) -> Workgroup:
    if ctx.workgroup is None:
        raise ValidationFailed("Open or create a workgroup first.")
    return ctx.workgroup


def money(kobo: int) -> str:
    return format_naira(kobo, with_kobo=kobo % 100 != 0)


async def _resolve_staff(ctx: ToolContext, needle: str):
    matches = await staff.find_staff(ctx.session, _wg(ctx).id, needle)
    matches = [m for m in matches if m.status != "inactive"] or matches
    if not matches:
        raise NotFound(f"No staff member matches “{needle}”.")
    if len(matches) > 1:
        exact = [m for m in matches if m.display_name.lower() == needle.strip().lower()]
        if len(exact) == 1:
            return exact[0]
        options = ", ".join(f"{m.display_name or 'Unregistered'} ({m.staff_code})" for m in matches[:6])
        raise ValidationFailed(f"“{needle}” matches several staff: {options}. Ask the user which one, using the staff ID.")
    return matches[0]


def _staff_brief(member) -> dict[str, Any]:
    return {
        "id": str(member.id),
        "staff_id": member.staff_code,
        "name": member.display_name or None,
        "status": member.status,
        "role": member.role.name if member.role else None,
        "salary": money(member.effective_salary_kobo),
        "bank": f"{member.bank_name} ••••{member.account_number[-4:]}" if member.account_number else None,
        "bank_name_matches": member.name_match,
        "ready_to_pay": member.payout_ready,
    }


async def _resolve_run(ctx: ToolContext, ref: str | None) -> PayrollRun:
    wg = _wg(ctx)
    stmt = select(PayrollRun).where(PayrollRun.workgroup_id == wg.id)
    if ref:
        try:
            stmt = stmt.where(PayrollRun.id == uuid.UUID(ref))
        except ValueError:
            stmt = stmt.where(PayrollRun.number == ref.strip().upper())
    else:
        stmt = stmt.where(PayrollRun.status.in_(["draft", "awaiting_funding", "ready"]))
    run = (await ctx.session.execute(stmt.order_by(PayrollRun.created_at.desc()).limit(1))).scalar_one_or_none()
    if run is None:
        raise NotFound("No matching payroll run." if ref else "There is no payroll waiting to be disbursed.")
    return run


# ====================================================================== READ
@tool("get_overview", "Snapshot of the open workgroup: wallet balance, staff counts, estimated payroll, next payday, subscription and setup checklist.")
async def get_overview(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    data = await workgroups.overview(ctx.session, _wg(ctx))
    wg = data["workgroup"]
    return {
        "workgroup": wg["name"],
        "wallet_balance": money(data["wallet_balance_kobo"]),
        "staff": data["staff"],
        "seats": wg["headcount"],
        "estimated_payroll_total": money(data["estimate"]["total_kobo"]),
        "estimated_salaries": money(data["estimate"]["salaries_kobo"]),
        "shortfall": money(data["shortfall_kobo"]),
        "payment_mode": wg["payment_mode"],
        "next_payday": wg["next_payday_at"].isoformat() if wg["next_payday_at"] else None,
        "subscription": {k: data["subscription"][k] for k in ("status", "seats", "days_left")} | {"plan": data["subscription"]["plan"]["name"]} if data["subscription"] else None,
        "checklist": [{"step": c["label"], "done": c["done"]} for c in data["checklist"]],
    }


@tool("list_workgroups", "List every workgroup the user manages.", needs_workgroup=False)
async def list_workgroups(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    items = await workgroups.list_for_user(ctx.session, ctx.user)
    return {"workgroups": [{"name": w.name, "staff_seats": w.headcount, "wallet_balance": money(w.wallet_balance_kobo),
                            "is_open_in_app": ctx.workgroup is not None and w.id == ctx.workgroup.id} for w in items]}


@tool(
    "list_staff",
    "List staff in the open workgroup, optionally filtered.",
    properties={
        "status": {"type": "string", "enum": ["registered", "pending", "inactive"], "description": "pending = staff ID not yet claimed"},
        "search": {"type": "string", "description": "Name, staff ID, email or account number"},
        "needs_attention": {"type": "boolean", "description": "Only registered staff whose bank name doesn't match or can't be paid"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    },
)
async def list_staff_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    items, total = await staff.list_staff(ctx.session, _wg(ctx).id, status=args.get("status"), query=args.get("search"),
                                          attention=bool(args.get("needs_attention")), page_size=int(args.get("limit") or 20))
    return {"total": total, "showing": len(items), "staff": [_staff_brief(m) for m in items]}


@tool("find_staff", "Look up a staff member by staff ID or name.", properties={"query": {"type": "string"}}, required=["query"])
async def find_staff_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    matches = await staff.find_staff(ctx.session, _wg(ctx).id, args["query"])
    return {"matches": [_staff_brief(m) for m in matches[:8]]}


@tool("get_wallet", "Wallet balance, funding account number (if any) and the latest transactions.")
async def get_wallet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    wg = _wg(ctx)
    entries = (
        await ctx.session.execute(select(WalletEntry).where(WalletEntry.workgroup_id == wg.id).order_by(WalletEntry.created_at.desc()).limit(8))
    ).scalars().all()
    return {
        "balance": money(wg.wallet_balance_kobo),
        "funding_account": {"bank": wg.dva_bank_name, "account_number": wg.dva_account_number, "account_name": wg.dva_account_name} if wg.dva_account_number else None,
        "recent": [{"date": e.created_at.date().isoformat(), "type": e.entry_type, "direction": e.direction, "amount": money(e.amount_kobo),
                    "description": e.description} for e in entries],
    }


@tool("list_payroll_runs", "Recent payroll runs with status and totals.", properties={"limit": {"type": "integer", "minimum": 1, "maximum": 20}})
async def list_runs(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    runs = (
        await ctx.session.execute(
            select(PayrollRun).where(PayrollRun.workgroup_id == _wg(ctx).id).order_by(PayrollRun.created_at.desc()).limit(int(args.get("limit") or 8))
        )
    ).scalars().all()
    return {"runs": [{"id": str(r.id), "number": r.number, "period": r.period_label, "status": r.status, "staff": r.staff_count,
                      "total": money(r.total_kobo), "paid": money(r.paid_kobo), "created": r.created_at.date().isoformat()} for r in runs]}


@tool("get_payroll_run", "Details of one payroll run, including each staff payment. Omit `run` for the run awaiting action.",
      properties={"run": {"type": "string", "description": "Run number like PAY-2610-ABC123 or its id"}})
async def get_run(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    run = await _resolve_run(ctx, args.get("run"))
    items = await payroll.load_items(ctx.session, run.id)
    return {
        "id": str(run.id), "number": run.number, "status": run.status, "period": run.period_label,
        "salaries": money(run.salaries_kobo), "transfer_fees": money(run.transfer_fees_kobo), "service_fee": money(run.commission_kobo),
        "total": money(run.total_kobo), "paid": money(run.paid_kobo), "refunded": money(run.refunded_kobo),
        "payments": [{"staff": i.staff_name, "staff_id": i.staff_code, "amount": money(i.amount_kobo), "status": i.status,
                      "failure_reason": i.failure_reason} for i in items[:60]],
    }


@tool("preview_payroll", "What paying everyone now would cost: salaries, Paystack transfer fees, the Streixpei service fee, total and shortfall, plus staff who can't be paid yet.")
async def preview_payroll(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    data = await payroll.preview(ctx.session, _wg(ctx))
    return {
        "payable_staff": len(data["items"]), "salaries": money(data["salaries_kobo"]), "transfer_fees": money(data["transfer_fees_kobo"]),
        "service_fee": f"{money(data['commission_kobo'])} ({data['commission_label']})", "total": money(data["total_kobo"]),
        "wallet_balance": money(data["wallet_balance_kobo"]), "shortfall": money(data["shortfall_kobo"]),
        "not_ready": [{"staff": n["staff_name"] or n["staff_code"], "reasons": n["reasons"]} for n in data["not_ready"][:20]],
        "unregistered_staff_ids": data["unregistered_count"],
    }


@tool("get_onboarding_link", "The link (and QR code page) staff use to register their details.")
async def get_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    wg = _wg(ctx)
    return {"link": workgroups.join_url(wg), "accepting_registrations": wg.invite_active, "qr_code_page": "/app/onboarding"}


@tool("get_billing", "Current subscription plan, seats, status and renewal amount for the open workgroup.")
async def get_billing(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sub = await billing.subscription_out(ctx.session, _wg(ctx).subscription)
    if not sub:
        return {"subscription": None}
    return {"status": sub["status"], "usable": sub["usable"], "plan": sub["plan"]["name"], "seats": sub["seats"], "cycle": sub["billing_cycle"],
            "renewal_amount": money(sub["renewal_amount_kobo"]), "ends_at": sub["ends_at"].isoformat() if sub["ends_at"] else None,
            "days_left": sub["days_left"], "auto_renew_from_wallet": sub["auto_renew"]}


@tool("quote_price", "Subscription price for a given number of staff.", needs_workgroup=False,
      properties={"staff_count": {"type": "integer", "minimum": 1}, "billing_cycle": {"type": "string", "enum": ["monthly", "annual"]}},
      required=["staff_count"])
async def quote_price(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    q = await billing.quote(ctx.session, int(args["staff_count"]), args.get("billing_cycle") or "monthly")
    return {"plan": q["plan"]["name"], "monthly": money(q["monthly_kobo"]), "amount_due": money(q["amount_kobo"]),
            "months_covered": q["months_covered"], "per_staff": money(q["plan"]["per_staff_kobo"]),
            "base_fee": money(q["plan"]["base_fee_kobo"]), "service_fee_on_disbursements": q["commission_label"]}


@tool(
    "search_payments",
    "Find individual salary payments (e.g. 'what did we pay Ada in May', 'failed payments last month').",
    properties={
        "staff": {"type": "string", "description": "Staff name or ID"},
        "from_date": {"type": "string", "description": "YYYY-MM-DD"},
        "to_date": {"type": "string", "description": "YYYY-MM-DD"},
        "status": {"type": "string", "enum": ["success", "failed", "reversed", "processing"]},
    },
)
async def search_payments(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    wg = _wg(ctx)
    stmt = select(PayrollItem, PayrollRun).join(PayrollRun, PayrollRun.id == PayrollItem.run_id).where(PayrollItem.workgroup_id == wg.id)
    if args.get("staff"):
        like = f"%{args['staff'].strip().lower()}%"
        from sqlalchemy import func, or_

        stmt = stmt.where(or_(func.lower(PayrollItem.staff_name).like(like), func.lower(PayrollItem.staff_code).like(like)))
    for key, op in (("from_date", "ge"), ("to_date", "le")):
        if args.get(key):
            try:
                day = date.fromisoformat(args[key])
            except ValueError:
                raise ValidationFailed(f"{key} must be YYYY-MM-DD")
            moment = datetime.combine(day, time.min if op == "ge" else time.max, tzinfo=timezone.utc)
            stmt = stmt.where(PayrollItem.created_at >= moment if op == "ge" else PayrollItem.created_at <= moment)
    if args.get("status"):
        stmt = stmt.where(PayrollItem.status == args["status"])
    else:
        stmt = stmt.where(PayrollItem.status.in_(["success", "failed", "reversed", "processing"]))
    rows = (await ctx.session.execute(stmt.order_by(PayrollItem.created_at.desc()).limit(40))).all()
    total = sum(i.amount_kobo for i, _ in rows if i.status == "success")
    return {
        "count": len(rows), "total_paid": money(total),
        "payments": [{"date": (i.paid_at or i.created_at).date().isoformat(), "staff": i.staff_name, "staff_id": i.staff_code,
                      "amount": money(i.amount_kobo), "status": i.status, "payroll": r.number, "period": r.period_label,
                      "reference": i.reference, "failure_reason": i.failure_reason} for i, r in rows],
    }


@tool("navigate", "Open a page of the app for the user.", needs_workgroup=False,
      properties={"page": {"type": "string", "enum": ["dashboard", "staff", "staff_ids", "onboarding", "roles", "payroll", "wallet", "billing",
                                                       "analytics", "activity", "notifications", "settings"]}}, required=["page"])
async def navigate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    paths = {"dashboard": "/app", "staff_ids": "/app/staff-ids"}
    page = args["page"]
    return {"navigate": paths.get(page, f"/app/{page}"), "ok": True}


# ====================================================================== SAFE
@tool("create_payroll_draft", "Prepare a draft payroll for every payable staff member. Nothing is paid until the user disburses it.", kind="safe",
      properties={"note": {"type": "string"}})
async def create_draft(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    run = await payroll.create_run(ctx.session, _wg(ctx), ctx.user, trigger="assistant", note=args.get("note"))
    await payroll.submit(ctx.session, _wg(ctx), run, ctx.user)
    return {"run_number": run.number, "status": run.status, "staff": run.staff_count, "total": money(run.total_kobo),
            "open": f"/app/payroll/runs/{run.id}", "next_step": "Disburse it" if run.status == "ready" else "Fund the shortfall, then disburse"}


@tool("create_funding_link", "Create a Paystack payment link to top up the wallet. method 'transfer' shows a bank account number to pay into.",
      kind="safe", properties={"amount_naira": {"type": "number", "minimum": 100}, "method": {"type": "string", "enum": ["checkout", "transfer"]}},
      required=["amount_naira"])
async def funding_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ..payments import start_checkout

    wg = _wg(ctx)
    payment = await start_checkout(ctx.session, workgroup=wg, user=ctx.user, purpose="wallet", net_kobo=naira_to_kobo(args["amount_naira"]),
                                   channel=args.get("method") or "checkout")
    return {"pay_url": payment.authorization_url, "you_pay": money(payment.amount_kobo), "wallet_receives": money(payment.expected_net_kobo),
            "paystack_fee": money(payment.fee_estimate_kobo)}


# =================================================================== CONFIRM
@tool("set_salary", "Set one staff member's monthly salary (overrides their role salary).", kind="confirm",
      properties={"staff": {"type": "string", "description": "Staff ID or full name"}, "amount_naira": {"type": "number", "minimum": 0}},
      required=["staff", "amount_naira"])
async def set_salary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    member = await staff.get_staff(ctx.session, _wg(ctx).id, uuid.UUID(args["staff_uuid"]))
    await staff.update_staff(ctx.session, _wg(ctx), member, ctx.user, {"salary_kobo": args["salary_kobo"]})
    return {"ok": True, "staff": member.display_name, "salary": money(member.effective_salary_kobo)}


@preparer("set_salary")
async def _prep_salary(ctx: ToolContext, args: dict[str, Any]):
    member = await _resolve_staff(ctx, args["staff"])
    kobo = naira_to_kobo(args["amount_naira"])
    label = member.display_name or "unregistered staff"
    return (f"Set {label} ({member.staff_code}) salary to {money(kobo)}/month (currently {money(member.effective_salary_kobo)})",
            {"staff_uuid": str(member.id), "salary_kobo": kobo})


@tool("create_role", "Create a role / salary grade, e.g. 'Supervisors at 180,000'.", kind="confirm",
      properties={"name": {"type": "string"}, "salary_naira": {"type": "number", "minimum": 0}}, required=["name", "salary_naira"])
async def create_role_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    role = await roles.create_role(ctx.session, _wg(ctx), ctx.user, args["name"], args["salary_kobo"])
    return {"ok": True, "role": role.name, "salary": money(role.salary_kobo)}


@preparer("create_role")
async def _prep_role(ctx: ToolContext, args: dict[str, Any]):
    kobo = naira_to_kobo(args["salary_naira"])
    if await roles.find_role(ctx.session, _wg(ctx).id, args["name"]):
        raise ValidationFailed(f"A role called “{args['name']}” already exists.")
    return f"Create role “{args['name'].strip()}” with a salary of {money(kobo)}/month", {"name": args["name"].strip(), "salary_kobo": kobo}


@tool("set_role_salary", "Change the salary of a role; staff in the role without a personal override follow it.", kind="confirm",
      properties={"role": {"type": "string"}, "salary_naira": {"type": "number", "minimum": 0}}, required=["role", "salary_naira"])
async def set_role_salary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    role = await roles.get_role(ctx.session, _wg(ctx).id, uuid.UUID(args["role_id"]))
    await roles.update_role(ctx.session, _wg(ctx), role, ctx.user, {"salary_kobo": args["salary_kobo"]})
    return {"ok": True, "role": role.name, "salary": money(role.salary_kobo)}


@preparer("set_role_salary")
async def _prep_role_salary(ctx: ToolContext, args: dict[str, Any]):
    role = await roles.find_role(ctx.session, _wg(ctx).id, args["role"])
    if role is None:
        raise NotFound(f"There is no role called “{args['role']}”.")
    kobo = naira_to_kobo(args["salary_naira"])
    return f"Change {role.name} salary from {money(role.salary_kobo)} to {money(kobo)}/month", {"role_id": str(role.id), "salary_kobo": kobo}


@tool("assign_role", "Put a staff member in a role.", kind="confirm",
      properties={"staff": {"type": "string"}, "role": {"type": "string"}}, required=["staff", "role"])
async def assign_role(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    member = await staff.get_staff(ctx.session, _wg(ctx).id, uuid.UUID(args["staff_uuid"]))
    await staff.update_staff(ctx.session, _wg(ctx), member, ctx.user, {"role_id": uuid.UUID(args["role_id"])})
    return {"ok": True, "staff": member.display_name, "role": member.role.name if member.role else None, "salary": money(member.effective_salary_kobo)}


@preparer("assign_role")
async def _prep_assign(ctx: ToolContext, args: dict[str, Any]):
    member = await _resolve_staff(ctx, args["staff"])
    role = await roles.find_role(ctx.session, _wg(ctx).id, args["role"])
    if role is None:
        raise NotFound(f"There is no role called “{args['role']}”. Create it first.")
    return (f"Move {member.display_name or member.staff_code} into {role.name} ({money(role.salary_kobo)}/month)",
            {"staff_uuid": str(member.id), "role_id": str(role.id)})


@tool("generate_staff_ids", "Generate new unique staff IDs for staff who will register with the onboarding link.", kind="confirm",
      properties={"count": {"type": "integer", "minimum": 1, "maximum": 1000}}, required=["count"])
async def gen_ids(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    created = await staff.generate_ids(ctx.session, _wg(ctx), int(args["count"]), ctx.user)
    return {"ok": True, "created": len(created), "examples": [c.staff_code for c in created[:5]], "download_page": "/app/staff-ids"}


@preparer("generate_staff_ids")
async def _prep_ids(ctx: ToolContext, args: dict[str, Any]):
    count = int(args["count"])
    wg = _wg(ctx)
    used = await billing.seats_in_use(ctx.session, wg.id)
    if used + count > wg.headcount:
        raise ValidationFailed(f"Only {wg.headcount - used} of {wg.headcount} seats are free. The user must increase the staff count on the Billing page first.")
    return f"Generate {count} new staff ID(s) for {wg.name}", {"count": count}


@tool("update_payroll_schedule", "Change payment mode (manual/automatic) and/or the payday (day of month).", kind="confirm",
      properties={"payment_mode": {"type": "string", "enum": ["manual", "automatic"]}, "payday_day": {"type": "integer", "minimum": 1, "maximum": 31}})
async def update_schedule(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    wg = await workgroups.update_workgroup(ctx.session, _wg(ctx), ctx.user, {k: v for k, v in args.items() if v is not None})
    return {"ok": True, "payment_mode": wg.payment_mode, "payday_day": wg.payday_day, "next_payday": wg.next_payday_at.isoformat()}


@preparer("update_payroll_schedule")
async def _prep_schedule(ctx: ToolContext, args: dict[str, Any]):
    parts = []
    if args.get("payment_mode"):
        parts.append(f"payment mode → {args['payment_mode']}")
    if args.get("payday_day"):
        parts.append(f"payday → day {args['payday_day']} of each month")
    if not parts:
        raise ValidationFailed("Say what to change: payment_mode and/or payday_day.")
    clean = {k: args[k] for k in ("payment_mode", "payday_day") if args.get(k)}
    return "Update payroll schedule: " + ", ".join(parts), clean


@tool("disburse_payroll", "Disburse (pay out) a funded payroll run to staff bank accounts. Requires the user's password.", kind="confirm",
      requires_password=True, properties={"run": {"type": "string", "description": "Run number; omit for the run awaiting action"}})
async def disburse_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    run = await payroll.disburse(ctx.session, _wg(ctx).id, uuid.UUID(args["run_id"]), ctx.user)
    return {"ok": True, "run": run.number, "status": run.status, "paid": money(run.paid_kobo), "open": f"/app/payroll/runs/{run.id}"}


@preparer("disburse_payroll")
async def _prep_disburse(ctx: ToolContext, args: dict[str, Any]):
    run = await _resolve_run(ctx, args.get("run"))
    if run.status not in ("ready", "awaiting_funding", "draft"):
        raise ValidationFailed(f"Payroll {run.number} is {run.status} and can't be disbursed.")
    wg = _wg(ctx)
    if run.status == "draft":
        await payroll.submit(ctx.session, wg, run, ctx.user)
    if wg.wallet_balance_kobo < run.total_kobo:
        raise ValidationFailed(f"Payroll {run.number} needs {money(run.total_kobo)} but the wallet has {money(wg.wallet_balance_kobo)}. Offer to create a funding link for {money(run.total_kobo - wg.wallet_balance_kobo)}.")
    return f"Pay {run.staff_count} staff {money(run.salaries_kobo)} (total {money(run.total_kobo)} incl. fees) for payroll {run.number}", {"run_id": str(run.id)}


@tool("deactivate_staff", "Deactivate a staff member so they are no longer paid.", kind="confirm",
      properties={"staff": {"type": "string"}}, required=["staff"])
async def deactivate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    member = await staff.get_staff(ctx.session, _wg(ctx).id, uuid.UUID(args["staff_uuid"]))
    await staff.update_staff(ctx.session, _wg(ctx), member, ctx.user, {"status": "inactive"})
    return {"ok": True, "staff": member.display_name or member.staff_code, "status": member.status}


@preparer("deactivate_staff")
async def _prep_deactivate(ctx: ToolContext, args: dict[str, Any]):
    member = await _resolve_staff(ctx, args["staff"])
    return f"Deactivate {member.display_name or member.staff_code} ({member.staff_code}) — they won't be included in payroll", {"staff_uuid": str(member.id)}


@tool("set_onboarding_open", "Pause or resume the staff onboarding link.", kind="confirm",
      properties={"open": {"type": "boolean"}}, required=["open"])
async def toggle_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    wg = await workgroups.set_invite_active(ctx.session, _wg(ctx), ctx.user, bool(args["open"]))
    return {"ok": True, "accepting_registrations": wg.invite_active}


@preparer("set_onboarding_open")
async def _prep_toggle(ctx: ToolContext, args: dict[str, Any]):
    return ("Resume" if args["open"] else "Pause") + " the staff onboarding link", {"open": bool(args["open"])}


@tool("rotate_onboarding_link", "Replace the onboarding link and QR code with new ones; the old link stops working.", kind="confirm")
async def rotate_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    wg = await workgroups.rotate_invite(ctx.session, _wg(ctx), ctx.user)
    return {"ok": True, "new_link": workgroups.join_url(wg)}


@preparer("rotate_onboarding_link")
async def _prep_rotate(ctx: ToolContext, args: dict[str, Any]):
    return "Replace the onboarding link and QR code (the current link will stop working)", {}


@tool("email_onboarding_link", "Email the onboarding link to staff.", kind="confirm",
      properties={"emails": {"type": "array", "items": {"type": "string"}, "maxItems": 200}, "message": {"type": "string"}}, required=["emails"])
async def email_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    wg = _wg(ctx)
    for email in args["emails"]:
        queue_email(ctx.session, email, "staff_invite", {"company": wg.name, "manager_name": ctx.user.full_name,
                                                         "join_url": workgroups.join_url(wg), "message": args.get("message")})
    return {"ok": True, "sent": len(args["emails"])}


@preparer("email_onboarding_link")
async def _prep_email(ctx: ToolContext, args: dict[str, Any]):
    from email_validator import EmailNotValidError, validate_email

    emails = []
    for raw in args.get("emails") or []:
        try:
            emails.append(validate_email(raw.strip(), check_deliverability=False).normalized)
        except EmailNotValidError:
            raise ValidationFailed(f"“{raw}” isn't a valid email address.")
    if not emails:
        raise ValidationFailed("Provide at least one email address.")
    emails = sorted(set(emails))
    preview = ", ".join(emails[:3]) + (f" and {len(emails) - 3} more" if len(emails) > 3 else "")
    return f"Email the onboarding link to {preview}", {"emails": emails, "message": (args.get("message") or "")[:300] or None}


def tool_specs() -> list[dict[str, Any]]:
    return [t.spec() for t in REGISTRY.values()]


async def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    t = REGISTRY.get(name)
    if t is None:
        raise ValidationFailed(f"Unknown action {name}.")
    if t.needs_workgroup and ctx.workgroup is None:
        raise ValidationFailed("Open or create a workgroup first.")
    return await t.handler(ctx, args)


def describe_error(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.message
    return "That action failed unexpectedly."
