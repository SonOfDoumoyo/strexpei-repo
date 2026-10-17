"""Redis: refresh sessions, OTPs, rate limits, token blocklist, job locks, caches."""

from __future__ import annotations

import json
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from redis.asyncio import Redis

from .config import settings
from .errors import RateLimited
from .security import sha256_hex

redis: Redis = Redis.from_url(settings.REDIS_URL, decode_responses=True, health_check_interval=30)

PREFIX = "spx:"


def k(*parts: str) -> str:
    return PREFIX + ":".join(parts)


# ------------------------------------------------------------- rate limiting
async def hit_rate_limit(bucket: str, identity: str, limit: int, window_seconds: int) -> None:
    """Fixed-window limiter. Raises RateLimited when exceeded."""
    window = int(time.time() // window_seconds)
    key = k("rl", bucket, identity, str(window))
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds + 5)
    if count > limit:
        retry_after = window_seconds - int(time.time() % window_seconds)
        raise RateLimited(details={"retry_after_seconds": retry_after})


async def reset_rate_limit(bucket: str, identity: str, window_seconds: int) -> None:
    window = int(time.time() // window_seconds)
    await redis.delete(k("rl", bucket, identity, str(window)))


# ------------------------------------------------------------- distributed lock
@asynccontextmanager
async def redis_lock(name: str, ttl_seconds: int = 300) -> AsyncIterator[bool]:
    """Best-effort mutual exclusion across API workers. Yields True if acquired."""
    key = k("lock", name)
    token = secrets.token_hex(8)
    acquired = bool(await redis.set(key, token, nx=True, ex=ttl_seconds))
    try:
        yield acquired
    finally:
        if acquired:
            # Only release our own lock.
            script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
            try:
                await redis.eval(script, 1, key, token)
            except Exception:  # pragma: no cover - lock expiry covers this
                pass


# ----------------------------------------------------------- refresh sessions
REFRESH_GRACE_SECONDS = 30


class RefreshSession(dict):
    @property
    def user_id(self) -> uuid.UUID:
        return uuid.UUID(self["user_id"])


async def issue_refresh_token(user_id: uuid.UUID, remember: bool, family: str | None = None, meta: dict[str, Any] | None = None) -> tuple[str, int]:
    token = secrets.token_urlsafe(48)
    ttl = settings.REFRESH_TOKEN_TTL_DAYS * 86400 if remember else settings.REFRESH_TOKEN_SHORT_TTL_HOURS * 3600
    record = {
        "user_id": str(user_id),
        "family": family or uuid.uuid4().hex,
        "remember": remember,
        "created_at": int(time.time()),
        **(meta or {}),
    }
    h = sha256_hex(token)
    pipe = redis.pipeline()
    pipe.set(k("rt", h), json.dumps(record), ex=ttl)
    pipe.sadd(k("rtu", str(user_id)), h)
    pipe.expire(k("rtu", str(user_id)), settings.REFRESH_TOKEN_TTL_DAYS * 86400 + 3600)
    await pipe.execute()
    return token, ttl


async def rotate_refresh_token(token: str) -> tuple[RefreshSession, str, int] | None:
    """Consume a refresh token and issue its successor.

    A rotated token stays valid for a short grace period so two browser tabs
    refreshing at the same moment don't log each other out. Presenting a token
    after its grace period is treated as theft and revokes every session of
    the user.
    """
    h = sha256_hex(token)
    raw = await redis.get(k("rt", h))
    if raw is None:
        used_by = await redis.get(k("rtused", h))
        if used_by:
            await revoke_all_refresh_tokens(uuid.UUID(used_by))
        return None
    record = RefreshSession(json.loads(raw))
    if record.get("rotated"):
        # Inside the grace window: hand out another token from the same family.
        pass
    else:
        record["rotated"] = True
        pipe = redis.pipeline()
        pipe.set(k("rt", h), json.dumps(record), ex=REFRESH_GRACE_SECONDS)
        pipe.set(k("rtused", h), record["user_id"], ex=settings.REFRESH_TOKEN_TTL_DAYS * 86400)
        await pipe.execute()
    meta = {key: value for key, value in record.items() if key not in {"user_id", "family", "remember", "created_at", "rotated"}}
    new_token, ttl = await issue_refresh_token(record.user_id, bool(record.get("remember")), record.get("family"), meta)
    return record, new_token, ttl


async def revoke_refresh_token(token: str) -> None:
    h = sha256_hex(token)
    raw = await redis.get(k("rt", h))
    await redis.delete(k("rt", h))
    if raw:
        record = json.loads(raw)
        await redis.srem(k("rtu", record["user_id"]), h)


async def revoke_all_refresh_tokens(user_id: uuid.UUID) -> None:
    key = k("rtu", str(user_id))
    hashes = await redis.smembers(key)
    if hashes:
        await redis.delete(*[k("rt", h) for h in hashes])
    await redis.delete(key)


# ----------------------------------------------------------- access blocklist
async def block_access_token(jti: str, exp: int) -> None:
    ttl = max(1, exp - int(time.time()))
    await redis.set(k("blk", jti), "1", ex=ttl)


async def is_access_token_blocked(jti: str) -> bool:
    return bool(await redis.exists(k("blk", jti)))


# ------------------------------------------------------------------- OTPs
OTP_MAX_ATTEMPTS = 5


async def store_otp(purpose: str, identity: str, code: str, ttl_seconds: int) -> None:
    key = k("otp", purpose, identity.lower())
    await redis.delete(key)
    await redis.hset(key, mapping={"code_hash": sha256_hex(code), "attempts": 0})
    await redis.expire(key, ttl_seconds)


async def verify_otp(purpose: str, identity: str, code: str) -> str:
    """Returns 'ok', 'expired', 'locked' or 'invalid'."""
    key = k("otp", purpose, identity.lower())
    data = await redis.hgetall(key)
    if not data:
        return "expired"
    attempts = int(data.get("attempts", 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        await redis.delete(key)
        return "locked"
    if sha256_hex(code.strip()) != data.get("code_hash"):
        await redis.hincrby(key, "attempts", 1)
        return "invalid"
    await redis.delete(key)
    return "ok"


# ------------------------------------------------------------------ caching
async def cache_get_json(key: str) -> Any | None:
    raw = await redis.get(k("cache", key))
    return json.loads(raw) if raw else None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    await redis.set(k("cache", key), json.dumps(value), ex=ttl_seconds)
