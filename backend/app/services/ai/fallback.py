"""Rule-based SPI used when no AI key is configured.

Covers the everyday commands so the assistant is useful out of the box.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Awaitable, Callable

from ...core.errors import AppError
from ...models import AIAction
from .tools import ToolContext, run_tool

Proposer = Callable[[ToolContext, uuid.UUID, str, dict[str, Any]], Awaitable[tuple[dict[str, Any], AIAction | None]]]

AMOUNT = r"₦?\s*([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?"

HELP = (
    "I'm running in basic mode, so I understand direct commands like:\n"
    "• “wallet balance” · “how many staff” · “preview payroll”\n"
    "• “generate 10 staff IDs” · “onboarding link”\n"
    "• “set salary of ACM-7K3M-Q9TD to 150,000”\n"
    "• “prepare payroll” · “disburse payroll” · “fund 500,000”\n"
    "• “payday on 28” · “switch to automatic” · “failed payments”"
)


def _amount(match_value: str, unit: str | None) -> float:
    value = float(match_value.replace(",", ""))
    unit = (unit or "").lower()
    if unit in ("k", "thousand"):
        value *= 1_000
    elif unit in ("m", "million"):
        value *= 1_000_000
    return value


async def respond(ctx: ToolContext, conversation_id: uuid.UUID, text: str, propose: Proposer) -> tuple[str, list[AIAction], str | None]:
    t = text.strip()
    low = t.lower()
    actions: list[AIAction] = []

    async def do(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        async with ctx.session.begin_nested():
            return await run_tool(ctx, name, args or {})

    async def ask(name: str, args: dict[str, Any]) -> str:
        output, action = await propose(ctx, conversation_id, name, args)
        if action:
            actions.append(action)
        return f"{output['will_do']}. Confirm it on the card below" + (" with your password." if action and action.requires_password else ".")

    try:
        if ctx.workgroup is None and not re.search(r"\bhelp\b|price|cost", low):
            return "Create a workgroup first — then I can manage staff, IDs and payroll for you.", actions, "/app/workgroups/new"

        if re.search(r"\b(help|what can you do|commands?)\b", low):
            return HELP, actions, None

        m = re.search(r"generate\s+(\d+)\s*(?:more\s+)?(?:staff\s*)?(?:ids?|codes?)", low)
        if m:
            return await ask("generate_staff_ids", {"count": int(m.group(1))}), actions, None

        m = re.search(r"(?:set|change|update)\s+(?:the\s+)?salary\s+(?:of|for)\s+(.+?)\s+to\s+" + AMOUNT, low)
        if m:
            name = t[m.start(1) : m.end(1)]
            return await ask("set_salary", {"staff": name, "amount_naira": _amount(m.group(2), m.group(3))}), actions, None

        m = re.search(r"(?:fund|top\s*up|load)\s+(?:the\s+)?(?:wallet\s+)?(?:with\s+)?" + AMOUNT, low)
        if m:
            method = "transfer" if "transfer" in low or "account number" in low else "checkout"
            out = await do("create_funding_link", {"amount_naira": _amount(m.group(1), m.group(2)), "method": method})
            return (f"Here's your payment link: you pay {out['you_pay']} (includes Paystack's {out['paystack_fee']} fee) and "
                    f"{out['wallet_receives']} lands in the wallet.\n{out['pay_url']}"), actions, None

        if re.search(r"\b(disburse|pay (?:the )?staff now|send (?:the )?salar)", low):
            return await ask("disburse_payroll", {}), actions, None

        if re.search(r"\b(prepare|create|start|run)\b.*\bpayroll\b", low):
            out = await do("create_payroll_draft", {})
            return (f"Payroll {out['run_number']} is prepared for {out['staff']} staff — total {out['total']}. "
                    f"Next step: {out['next_step'].lower()}."), actions, out["open"]

        if re.search(r"\b(preview|estimate|how much)\b.*\bpayroll\b|\bpayroll (cost|total)\b", low):
            out = await do("preview_payroll")
            return (f"Paying {out['payable_staff']} staff now costs {out['total']}: salaries {out['salaries']}, transfer fees "
                    f"{out['transfer_fees']}, service fee {out['service_fee']}. Wallet: {out['wallet_balance']}"
                    + (f", short by {out['shortfall']}." if out["shortfall"] not in ("₦0",) else ".")), actions, None

        m = re.search(r"payday\s+(?:on|to|=)?\s*(?:the\s+)?(\d{1,2})", low)
        if m:
            return await ask("update_payroll_schedule", {"payday_day": int(m.group(1))}), actions, None

        if re.search(r"\b(automatic|auto[- ]?pay)\b", low) and re.search(r"\b(switch|set|turn|enable|make|use)\b", low):
            return await ask("update_payroll_schedule", {"payment_mode": "automatic"}), actions, None
        if re.search(r"\bmanual\b", low) and re.search(r"\b(switch|set|turn|make|use)\b", low):
            return await ask("update_payroll_schedule", {"payment_mode": "manual"}), actions, None

        if re.search(r"\b(balance|wallet)\b", low):
            out = await do("get_wallet")
            extra = ""
            if out["funding_account"]:
                fa = out["funding_account"]
                extra = f" Fund it by transfer to {fa['bank']} {fa['account_number']}."
            return f"Your wallet balance is {out['balance']}.{extra}", actions, None

        if re.search(r"\bfail(ed|ures?)\b", low):
            out = await do("search_payments", {"status": "failed"})
            if not out["count"]:
                return "No failed payments — every transfer went through.", actions, None
            lines = [f"• {p['staff']} — {p['amount']} ({p['payroll']}): {p['failure_reason']}" for p in out["payments"][:8]]
            return "Failed payments:\n" + "\n".join(lines), actions, "/app/payroll"

        if re.search(r"\b(link|qr|onboard|invite)\b", low):
            out = await do("get_onboarding_link")
            state = "open" if out["accepting_registrations"] else "paused"
            return f"Your onboarding link ({state}) is:\n{out['link']}\nThe QR code is on the Onboarding page.", actions, "/app/onboarding"

        if re.search(r"\b(staff|employees?|team|people)\b", low):
            out = await do("get_overview")
            s = out["staff"]
            return (f"{out['workgroup']} has {s['registered']} registered staff, {s['pending']} unclaimed staff IDs and "
                    f"{s['payout_ready']} ready to be paid (seats: {out['seats']})."), actions, None

        if re.search(r"\b(subscription|plan|billing|renew)\b", low):
            out = await do("get_billing")
            return (f"You're on the {out['plan']} plan for {out['seats']} staff ({out['status']}). "
                    f"Renewal: {out['renewal_amount']}" + (f", {out['days_left']} days left." if out.get("days_left") is not None else ".")), actions, "/app/billing"
    except AppError as exc:
        return exc.message, actions, None

    return "I didn't catch that. " + HELP, actions, None
