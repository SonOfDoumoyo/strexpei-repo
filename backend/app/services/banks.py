from __future__ import annotations

import logging
import re

from ..core.redis import cache_get_json, cache_set_json
from .paystack import FALLBACK_BANKS, PaystackError, get_provider

logger = logging.getLogger("streixpei.banks")

CACHE_KEY = "banks:ng:v1"


async def list_banks() -> list[dict[str, str]]:
    cached = await cache_get_json(CACHE_KEY)
    if cached:
        return cached
    try:
        banks = await get_provider().list_banks()
        if banks:
            await cache_set_json(CACHE_KEY, banks, 24 * 3600)
            return banks
    except (PaystackError, Exception) as exc:  # network failures fall back to a static list
        logger.warning("Bank list unavailable from provider: %s", exc)
    return [dict(b) for b in FALLBACK_BANKS]


async def bank_name(code: str) -> str | None:
    for bank in await list_banks():
        if bank["code"] == code:
            return bank["name"]
    return None


_TOKEN = re.compile(r"[a-z]+")


def names_match(account_name: str, *names: str | None) -> bool:
    """True when at least one supplied name appears in the bank account name."""
    account_tokens = set(_TOKEN.findall(account_name.lower()))
    supplied = {t for n in names if n for t in _TOKEN.findall(n.lower()) if len(t) > 1}
    return bool(account_tokens & supplied)
