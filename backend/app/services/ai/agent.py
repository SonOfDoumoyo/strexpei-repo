"""SPI — the Streixpei assistant.

Runs a tool-use loop against Claude (Anthropic Messages API). Read tools
execute straight away; tools that change data become pending actions the
user confirms in the UI. When no API key is configured a small rule-based
interpreter handles the most common commands so the assistant still works.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.errors import AppError, Conflict, NotFound, PaymentRequired, Unauthorized
from ...core.security import verify_password
from ...core.timeutil import utcnow
from ...models import AIAction, AIMessage, Plan, User, Workgroup
from .. import billing, platform
from ..activity import audit
from . import fallback
from .tools import REGISTRY, ToolContext, describe_error, run_tool, tool_specs

logger = logging.getLogger("streixpei.ai")

MAX_STEPS = 6
HISTORY_LIMIT = 24
ACTION_TTL = timedelta(minutes=30)

SYSTEM_PROMPT = """You are SPI, the built-in assistant of {app_name} — a payroll platform for Nigerian businesses made by {company}.
You help finance managers run payroll by answering questions and taking actions with the tools provided.

Context
- Signed-in manager: {user_name}
- Workgroup open in the app: {workgroup}
- Today: {today}
- Money is Nigerian Naira (₦). Tools return formatted amounts — quote them exactly; never do your own fee maths.
- {app_name} charges a {commission} service fee on salaries disbursed, plus Paystack transfer fees. Wallet top-ups by card/transfer include Paystack's collection fee.
- Staff never create accounts: they register through the workgroup's onboarding link or QR code using their staff ID.

How to work
- Use tools to look things up instead of guessing. If a request is ambiguous (e.g. two staff share a name), ask a short question.
- Actions that change data are proposed to the user as a confirmation card. When a tool result says an action is awaiting confirmation, tell the user in one sentence what will happen and that they can confirm it on the card. Never claim it is done before it is confirmed.
- Disbursing money always needs the user's confirmation and password. Never pressure the user to pay.
- You can't withdraw money from the wallet. If asked, point the user to Wallet → Withdraw (use the navigate tool); it asks for their password.
- Keep answers short and scannable: one or two sentences, or a compact list for several items. No tables wider than 4 columns.
- You only act on the open workgroup. If the user asks about another workgroup, tell them to switch to it first.
- Refuse requests unrelated to payroll, staff, payments or this app politely, in one sentence.
"""


# ------------------------------------------------------------- persistence
async def _history(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[AIMessage]:
    rows = (
        await session.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id, AIMessage.user_id == user_id)
            .order_by(AIMessage.created_at.desc())
            .limit(HISTORY_LIMIT)
        )
    ).scalars().all()
    return list(reversed(rows))


def _to_api_messages(rows: list[AIMessage]) -> list[dict[str, Any]]:
    """Merges consecutive same-role messages and drops a leading assistant turn."""
    messages: list[dict[str, Any]] = []
    for row in rows:
        content = row.content if isinstance(row.content, list) else [{"type": "text", "text": str(row.content)}]
        if messages and messages[-1]["role"] == row.role:
            messages[-1]["content"] = messages[-1]["content"] + content
        else:
            messages.append({"role": row.role, "content": list(content)})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    # A tool_result must follow its tool_use; if history was truncated mid-pair, drop orphans.
    if messages and any(b.get("type") == "tool_result" for b in messages[0]["content"]):
        messages[0]["content"] = [b for b in messages[0]["content"] if b.get("type") != "tool_result"] or [{"type": "text", "text": "(continued)"}]
    return messages


def _save(session: AsyncSession, conversation_id: uuid.UUID, user: User, workgroup: Workgroup | None, role: str, content: list[dict[str, Any]],
          visible: str | None = None, quota: bool = False) -> AIMessage:
    message = AIMessage(conversation_id=conversation_id, user_id=user.id, workgroup_id=workgroup.id if workgroup else None, role=role,
                        content=content, visible_text=visible, counts_toward_quota=quota)
    session.add(message)
    return message


# ----------------------------------------------------------------- quota
async def quota_status(session: AsyncSession, user: User, workgroup: Workgroup | None) -> dict[str, Any]:
    start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = (
        await session.execute(
            select(func.count()).select_from(AIMessage).where(
                AIMessage.user_id == user.id, AIMessage.counts_toward_quota.is_(True), AIMessage.created_at >= start,
                AIMessage.workgroup_id == (workgroup.id if workgroup else None) if workgroup else AIMessage.workgroup_id.is_(None),
            )
        )
    ).scalar_one()
    limit = await platform.get_int(session, "trial_ai_quota")
    if workgroup and workgroup.subscription:
        sub = workgroup.subscription
        if sub.status in ("active", "past_due"):
            plan = sub.plan or await session.get(Plan, sub.plan_code)
            limit = plan.ai_monthly_quota
    return {"used": int(used), "limit": int(limit), "remaining": max(0, int(limit) - int(used))}


# ----------------------------------------------------------------- model
async def _call_claude(system: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.ANTHROPIC_BASE_URL, timeout=httpx.Timeout(60, connect=10)) as client:
        response = await client.post(
            "/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": settings.AI_MODEL, "max_tokens": settings.AI_MAX_TOKENS, "system": system, "tools": tool_specs(), "messages": messages},
        )
    if response.status_code >= 400:
        logger.error("Claude API error %s: %s", response.status_code, response.text[:500])
        raise AppError("SPI is having trouble thinking right now. Please try again in a moment.", code="ai_unavailable", status_code=503)
    return response.json()


def _action_out(action: AIAction) -> dict[str, Any]:
    tool = REGISTRY.get(action.tool)
    return {
        "id": str(action.id),
        "tool": action.tool,
        "summary": action.summary,
        "requires_password": action.requires_password,
        "status": action.status,
        "kind": tool.kind if tool else "confirm",
        "result": action.result,
        "created_at": action.created_at,
    }


async def _propose(ctx: ToolContext, conversation_id: uuid.UUID, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], AIAction | None]:
    tool = REGISTRY[name]
    summary, normalized = await tool.prepare(ctx, args) if tool.prepare else (name, args)
    action = AIAction(conversation_id=conversation_id, user_id=ctx.user.id, workgroup_id=ctx.workgroup.id, tool=name, args=normalized,
                      summary=summary[:255], requires_password=tool.requires_password)
    ctx.session.add(action)
    await ctx.session.flush()
    return {"status": "awaiting_user_confirmation", "action_id": str(action.id), "will_do": summary,
            "note": "Shown to the user as a confirmation card" + (" (password required)" if tool.requires_password else "")}, action


async def chat(session: AsyncSession, user: User, workgroup: Workgroup | None, message: str, conversation_id: uuid.UUID | None, ip: str | None) -> dict[str, Any]:
    quota = await quota_status(session, user, workgroup)
    if quota["remaining"] <= 0:
        raise PaymentRequired(
            f"You've used all {quota['limit']} SPI requests for this month on your plan. Upgrade or wait until next month.", code="ai_quota_exceeded"
        )
    conversation_id = conversation_id or uuid.uuid4()
    ctx = ToolContext(session=session, user=user, workgroup=workgroup, ip=ip)
    actions: list[AIAction] = []
    navigate: str | None = None

    _save(session, conversation_id, user, workgroup, "user", [{"type": "text", "text": message}], visible=message, quota=True)
    await session.flush()

    if not settings.ai_configured:
        reply, actions, navigate = await fallback.respond(ctx, conversation_id, message, _propose)
        _save(session, conversation_id, user, workgroup, "assistant", [{"type": "text", "text": reply}], visible=reply)
        await session.commit()
        return {"conversation_id": str(conversation_id), "reply": reply, "actions": [_action_out(a) for a in actions], "navigate": navigate,
                "mode": "basic", "quota": await quota_status(session, user, workgroup)}

    fees = await platform.get_fees(session)
    from ...core.money import bps_label

    system = SYSTEM_PROMPT.format(
        app_name=settings.APP_NAME,
        company=settings.COMPANY_NAME,
        user_name=user.full_name,
        workgroup=f"{workgroup.name} ({workgroup.headcount} seats)" if workgroup else "none — the user hasn't created or opened one",
        today=utcnow().strftime("%A %d %B %Y"),
        commission=bps_label(fees.commission_bps),
    )
    reply_parts: list[str] = []
    for _ in range(MAX_STEPS):
        messages = _to_api_messages(await _history(session, conversation_id, user.id))
        response = await _call_claude(system, messages)
        content = response.get("content") or []
        _save(session, conversation_id, user, workgroup, "assistant", content,
              visible="\n".join(b.get("text", "") for b in content if b.get("type") == "text").strip() or None)
        await session.flush()
        reply_parts.extend(b["text"] for b in content if b.get("type") == "text" and b.get("text"))
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if response.get("stop_reason") != "tool_use" or not tool_uses:
            break
        results = []
        for block in tool_uses:
            name, args = block.get("name"), block.get("input") or {}
            tool = REGISTRY.get(name)
            try:
                if tool is None:
                    raise AppError(f"Unknown tool {name}")
                if tool.needs_workgroup and workgroup is None:
                    raise AppError("No workgroup is open. Ask the user to create or open one first.")
                if tool.kind == "confirm":
                    output, action = await _propose(ctx, conversation_id, name, args)
                    if action:
                        actions.append(action)
                else:
                    async with session.begin_nested():
                        output = await run_tool(ctx, name, args)
                    if isinstance(output, dict) and output.get("navigate"):
                        navigate = output["navigate"]
                results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(output, default=str)[:12000]})
            except Exception as exc:  # report tool errors back to the model
                if not isinstance(exc, AppError):
                    logger.exception("Tool %s crashed", name)
                results.append({"type": "tool_result", "tool_use_id": block["id"], "content": describe_error(exc), "is_error": True})
        _save(session, conversation_id, user, workgroup, "user", results)
        await session.flush()
    reply = "\n\n".join(p.strip() for p in reply_parts if p.strip()) or "Done."
    await session.commit()
    return {"conversation_id": str(conversation_id), "reply": reply, "actions": [_action_out(a) for a in actions], "navigate": navigate,
            "mode": "ai", "quota": await quota_status(session, user, workgroup)}


async def resolve_action(session: AsyncSession, user: User, action_id: uuid.UUID, confirm: bool, password: str | None, ip: str | None) -> dict[str, Any]:
    action = (await session.execute(select(AIAction).where(AIAction.id == action_id).with_for_update())).scalar_one_or_none()
    if action is None or action.user_id != user.id:
        raise NotFound("Action not found.")
    if action.status != "pending":
        raise Conflict(f"This action was already {action.status}.")
    if utcnow() - action.created_at > ACTION_TTL:
        action.status = "expired"
        await session.commit()
        raise Conflict("This action expired. Ask SPI again.")
    workgroup = await session.get(Workgroup, action.workgroup_id)
    if workgroup is None or workgroup.owner_id != user.id:
        raise NotFound("Action not found.")
    action.resolved_at = utcnow()
    if not confirm:
        action.status = "canceled"
        _save(session, action.conversation_id, user, workgroup, "user",
              [{"type": "text", "text": f"[The user cancelled the action: {action.summary}]"}])
        await session.commit()
        return {"action": _action_out(action), "message": "Cancelled."}
    tool = REGISTRY[action.tool]
    if tool.requires_password:
        if not password or not await verify_password(password, user.password_hash):
            action.resolved_at = None
            raise Unauthorized("Incorrect password.", code="invalid_password")
    ctx = ToolContext(session=session, user=user, workgroup=workgroup, ip=ip)
    try:
        if action.tool == "disburse_payroll":
            await session.commit()  # disburse manages its own transactions
            result = await run_tool(ctx, action.tool, action.args)
            action = await session.get(AIAction, action_id)
        else:
            result = await run_tool(ctx, action.tool, action.args)
        action.status = "executed"
        action.result = json.loads(json.dumps(result, default=str))
        message = "Done — " + action.summary[0].lower() + action.summary[1:]
    except AppError as exc:
        await session.rollback()
        action = await session.get(AIAction, action_id)
        action.status = "failed"
        action.resolved_at = utcnow()
        action.result = {"error": exc.message}
        message = exc.message
    audit(session, action="assistant.action", summary=f"SPI: {action.summary} ({action.status})", actor=user, workgroup_id=workgroup.id,
          meta={"tool": action.tool}, ip=ip)
    _save(session, action.conversation_id, user, workgroup, "user",
          [{"type": "text", "text": f"[Action {action.status}: {action.summary}. Result: {json.dumps(action.result, default=str)[:1500]}]"}])
    await session.commit()
    return {"action": _action_out(action), "message": message}


async def conversation(session: AsyncSession, user: User, conversation_id: uuid.UUID | None, workgroup: Workgroup | None) -> dict[str, Any]:
    if conversation_id is None:
        latest = (
            await session.execute(
                select(AIMessage.conversation_id).where(
                    AIMessage.user_id == user.id, AIMessage.workgroup_id == (workgroup.id if workgroup else None)
                ).order_by(AIMessage.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if latest is None:
            return {"conversation_id": None, "messages": [], "actions": [], "quota": await quota_status(session, user, workgroup),
                    "mode": "ai" if settings.ai_configured else "basic"}
        conversation_id = latest
    rows = (
        await session.execute(
            select(AIMessage).where(AIMessage.conversation_id == conversation_id, AIMessage.user_id == user.id,
                                    AIMessage.visible_text.is_not(None)).order_by(AIMessage.created_at).limit(100)
        )
    ).scalars().all()
    actions = (
        await session.execute(select(AIAction).where(AIAction.conversation_id == conversation_id, AIAction.user_id == user.id).order_by(AIAction.created_at))
    ).scalars().all()
    return {
        "conversation_id": str(conversation_id),
        "messages": [{"id": str(r.id), "role": r.role, "text": r.visible_text, "created_at": r.created_at} for r in rows],
        "actions": [_action_out(a) for a in actions],
        "quota": await quota_status(session, user, workgroup),
        "mode": "ai" if settings.ai_configured else "basic",
    }
