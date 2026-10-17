from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request

from ...core.redis import hit_rate_limit
from ...schemas.requests import AIActionIn, AIChatIn
from ...services import workgroups as workgroup_service
from ...services.ai import agent
from ..deps import Manager, SessionDep, client_ip

router = APIRouter(prefix="/ai", tags=["assistant"])


@router.post("/chat")
async def chat(body: AIChatIn, request: Request, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("ai-chat", str(user.id), 30, 60)
    workgroup = await workgroup_service.get_owned(session, user, body.workgroup_id) if body.workgroup_id else None
    return await agent.chat(session, user, workgroup, body.message, body.conversation_id, client_ip(request))


@router.get("/conversation")
async def conversation(user: Manager, session: SessionDep, workgroup_id: uuid.UUID | None = None,
                       conversation_id: uuid.UUID | None = None) -> dict[str, Any]:
    workgroup = await workgroup_service.get_owned(session, user, workgroup_id) if workgroup_id else None
    return await agent.conversation(session, user, conversation_id, workgroup)


@router.post("/actions/{action_id}")
async def resolve_action(action_id: uuid.UUID, body: AIActionIn, request: Request, user: Manager, session: SessionDep) -> dict[str, Any]:
    await hit_rate_limit("ai-action", str(user.id), 30, 60)
    return await agent.resolve_action(session, user, action_id, body.confirm, body.password, client_ip(request))
