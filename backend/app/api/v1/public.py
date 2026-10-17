from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response, status

from ...core.config import settings
from ...core.database import SessionLocal
from ...core.errors import AppError, Unauthorized
from ...core.money import bps_label
from ...schemas.requests import JoinCheckIn, JoinRegisterIn, JoinResolveIn
from ...services import banks, join, platform, webhooks
from ...services.paystack import get_provider
from ..deps import SessionDep, client_ip

logger = logging.getLogger("streixpei.public")

router = APIRouter(tags=["public"])


@router.get("/meta")
async def meta(session: SessionDep) -> dict[str, Any]:
    fees = await platform.get_fees(session)
    return {
        "app_name": settings.APP_NAME,
        "company_name": settings.COMPANY_NAME,
        "support_email": settings.SUPPORT_EMAIL,
        "commission_bps": fees.commission_bps,
        "commission_label": bps_label(fees.commission_bps),
        "trial_days": await platform.get_int(session, "trial_days"),
        "annual_discount_months": await platform.get_int(session, "annual_discount_months"),
        "ai_mode": "ai" if settings.ai_configured else "basic",
        "payments_sandbox": settings.PAYMENTS_PROVIDER == "fake" or settings.PAYSTACK_SECRET_KEY.startswith("sk_test"),
        "fees": {
            "checkout": {"percent_bps": fees.checkout_percent_bps, "flat_kobo": fees.checkout_flat_kobo,
                         "flat_waived_below_kobo": fees.checkout_flat_waived_below_kobo, "cap_kobo": fees.checkout_cap_kobo},
            "transfer_bands": [{"up_to_kobo": b.up_to_kobo, "fee_kobo": b.fee_kobo} for b in fees.transfer_bands],
            "stamp_duty_kobo": fees.stamp_duty_kobo,
            "stamp_duty_threshold_kobo": fees.stamp_duty_threshold_kobo,
        },
    }


@router.get("/banks")
async def list_banks() -> list[dict[str, str]]:
    return [{"name": b["name"], "code": b["code"]} for b in await banks.list_banks()]


# ------------------------------------------------------------ staff onboarding
@router.get("/join/{invite_code}")
async def join_info(invite_code: str, session: SessionDep) -> dict[str, Any]:
    return await join.public_info(session, invite_code)


@router.post("/join/{invite_code}/verify-id")
async def join_verify_id(invite_code: str, body: JoinCheckIn, request: Request, session: SessionDep) -> dict[str, Any]:
    return await join.check_staff_id(session, invite_code, body.staff_code, client_ip(request))


@router.post("/join/{invite_code}/resolve-account")
async def join_resolve(invite_code: str, body: JoinResolveIn, request: Request, session: SessionDep) -> dict[str, Any]:
    return await join.resolve_account(session, invite_code, body.staff_code, body.account_number, body.bank_code, client_ip(request))


@router.post("/join/{invite_code}/register", status_code=status.HTTP_201_CREATED)
async def join_register(invite_code: str, body: JoinRegisterIn, request: Request, session: SessionDep) -> dict[str, Any]:
    result = await join.register(session, invite_code, body.model_dump(), client_ip(request))
    await session.commit()
    return result


# --------------------------------------------------------------------- webhooks
@router.post("/webhooks/paystack", include_in_schema=False)
async def paystack_webhook(request: Request) -> Response:
    body = await request.body()
    if not get_provider().verify_signature(body, request.headers.get("x-paystack-signature")):
        raise Unauthorized("Invalid signature.", code="bad_signature")
    try:
        payload = json.loads(body)
    except ValueError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    async with SessionLocal() as session:
        try:
            outcome = await webhooks.handle_paystack(session, payload)
            await session.commit()
        except AppError as exc:
            await session.rollback()
            logger.warning("Webhook %s not applied: %s", payload.get("event"), exc.message)
            return Response(status_code=status.HTTP_200_OK)  # retrying won't help
        except Exception:
            await session.rollback()
            logger.exception("Webhook %s failed", payload.get("event"))
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)  # Paystack will retry
    logger.info("Paystack webhook %s → %s", payload.get("event"), outcome)
    if outcome in ("charge_applied", "dva_applied"):
        _kick_automatic_disbursements()
    return Response(status_code=status.HTTP_200_OK)


def _kick_automatic_disbursements() -> None:
    """Disburse automatic payrolls that just became funded, without waiting for the scheduler."""
    import asyncio

    from ...services import payroll

    async def _run() -> None:
        async with SessionLocal() as session:
            try:
                await payroll.disburse_ready_automatic(session)
            except Exception:
                logger.exception("Immediate automatic disbursement failed")

    try:
        task = asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        return
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


_BACKGROUND: set = set()
