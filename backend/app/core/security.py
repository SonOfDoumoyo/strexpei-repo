"""Password hashing, access tokens and signed one-off tokens."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

# ----------------------------------------------------------------- passwords
# scrypt (RFC 7914) from the standard library: memory-hard, no native
# dependencies to compile on deployment. Parameters follow OWASP guidance.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 128 * 1024 * 1024


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password_sync(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN, maxmem=_SCRYPT_MAXMEM
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password_sync(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if algo != "scrypt":
            return False
        expected = _unb64(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# Used to keep login timing constant when the email does not exist.
DUMMY_PASSWORD_HASH = hash_password_sync(secrets.token_urlsafe(16))


async def hash_password(password: str) -> str:
    """Runs scrypt in a worker thread so the event loop keeps serving requests."""
    return await asyncio.to_thread(hash_password_sync, password)


async def verify_password(password: str, encoded: str) -> bool:
    return await asyncio.to_thread(verify_password_sync, password, encoded)


# --------------------------------------------------------------- access JWT
def create_access_token(user_id: uuid.UUID, role: str, token_version: int) -> tuple[str, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)).timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, payload


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


# ---------------------------------------------------------- signed tokens
_serializer = URLSafeTimedSerializer(settings.JWT_SECRET_KEY, salt="streixpei.signed")


def create_signed_token(purpose: str, data: dict[str, Any]) -> str:
    return _serializer.dumps({"p": purpose, "d": data})


def read_signed_token(token: str, purpose: str, max_age_seconds: int) -> dict[str, Any] | None:
    try:
        raw = _serializer.loads(token, max_age=max_age_seconds)
    except (SignatureExpired, BadSignature):
        return None
    if not isinstance(raw, dict) or raw.get("p") != purpose:
        return None
    data = raw.get("d")
    return data if isinstance(data, dict) else None


# ------------------------------------------------------------- misc helpers
def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
