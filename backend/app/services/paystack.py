"""Paystack integration.

``PaystackClient`` talks to the real API. ``FakePaystack`` is a deterministic
stand-in for local development and automated tests (``PAYMENTS_PROVIDER=fake``)
— it is refused at start-up in production.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import random
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from ..core.config import settings
from ..core.redis import k, redis

logger = logging.getLogger("streixpei.paystack")


class PaystackError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, transient: bool = False, payload: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.transient = transient
        self.payload = payload


@dataclass
class TransferResult:
    reference: str
    transfer_code: str | None
    status: str  # pending | success | failed | reversed | otp | received | queued
    reason: str | None = None


class PaymentsProvider(Protocol):
    name: str

    async def list_banks(self) -> list[dict[str, Any]]: ...
    async def resolve_account(self, account_number: str, bank_code: str) -> str: ...
    async def create_recipient(self, name: str, account_number: str, bank_code: str) -> str: ...
    async def initialize_transaction(
        self, *, email: str, amount_kobo: int, reference: str, callback_url: str, metadata: dict[str, Any], channels: list[str] | None
    ) -> dict[str, Any]: ...
    async def verify_transaction(self, reference: str) -> dict[str, Any] | None: ...
    async def create_customer(self, *, email: str, first_name: str, last_name: str, phone: str | None) -> str: ...
    async def create_dedicated_account(self, customer_code: str) -> dict[str, Any]: ...
    async def bulk_transfer(self, transfers: list[dict[str, Any]]) -> list[TransferResult]: ...
    async def verify_transfer(self, reference: str) -> TransferResult | None: ...
    async def get_balance(self) -> int: ...
    def verify_signature(self, body: bytes, signature: str | None) -> bool: ...


# ---------------------------------------------------------------------------
# Real Paystack
# ---------------------------------------------------------------------------


class PaystackClient:
    name = "paystack"

    def __init__(self, secret_key: str, base_url: str, timeout: int = 30, transport: httpx.AsyncBaseTransport | None = None):
        self._secret = secret_key
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=10),
            headers={"Authorization": f"Bearer {secret_key}", "Content-Type": "application/json"},
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, params: dict | None = None, json_body: Any = None) -> Any:
        if not self._secret:
            raise PaystackError("Paystack is not configured (missing PAYSTACK_SECRET_KEY).", transient=False)
        try:
            response = await self._client.request(method, path, params=params, json=json_body)
        except httpx.TimeoutException as exc:
            raise PaystackError("Paystack timed out.", transient=True) from exc
        except httpx.HTTPError as exc:
            raise PaystackError(f"Could not reach Paystack: {exc.__class__.__name__}", transient=True) from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text[:200]}

        if response.status_code >= 500:
            raise PaystackError(payload.get("message") or "Paystack is unavailable.", status_code=response.status_code, transient=True, payload=payload)
        if response.status_code >= 400 or not payload.get("status", False):
            raise PaystackError(
                payload.get("message") or "Paystack rejected the request.", status_code=response.status_code, transient=False, payload=payload
            )
        return payload.get("data")

    async def list_banks(self) -> list[dict[str, Any]]:
        banks: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(10):
            params: dict[str, Any] = {"country": "nigeria", "currency": "NGN", "perPage": 100, "use_cursor": "true"}
            if cursor:
                params["next"] = cursor
            response = await self._client.get("/bank", params=params)
            payload = response.json()
            if response.status_code >= 400 or not payload.get("status"):
                raise PaystackError(payload.get("message") or "Could not load banks", transient=response.status_code >= 500)
            for bank in payload.get("data", []):
                if bank.get("active", True) and not bank.get("is_deleted") and bank.get("type", "nuban") == "nuban":
                    banks.append({"name": bank["name"], "code": bank["code"], "slug": bank.get("slug")})
            cursor = (payload.get("meta") or {}).get("next")
            if not cursor:
                break
        # Same bank can appear twice under different slugs; keep the first.
        seen: set[str] = set()
        unique = []
        for bank in sorted(banks, key=lambda b: b["name"].lower()):
            if bank["code"] in seen:
                continue
            seen.add(bank["code"])
            unique.append(bank)
        return unique

    async def resolve_account(self, account_number: str, bank_code: str) -> str:
        data = await self._request("GET", "/bank/resolve", params={"account_number": account_number, "bank_code": bank_code})
        name = (data or {}).get("account_name")
        if not name:
            raise PaystackError("We couldn't verify that account number.")
        return str(name).strip()

    async def create_recipient(self, name: str, account_number: str, bank_code: str) -> str:
        data = await self._request(
            "POST",
            "/transferrecipient",
            json_body={"type": "nuban", "name": name, "account_number": account_number, "bank_code": bank_code, "currency": "NGN"},
        )
        return data["recipient_code"]

    async def initialize_transaction(self, *, email, amount_kobo, reference, callback_url, metadata, channels) -> dict[str, Any]:
        body: dict[str, Any] = {
            "email": email,
            "amount": amount_kobo,
            "currency": "NGN",
            "reference": reference,
            "callback_url": callback_url,
            "metadata": metadata,
        }
        if channels:
            body["channels"] = channels
        data = await self._request("POST", "/transaction/initialize", json_body=body)
        return {"authorization_url": data["authorization_url"], "access_code": data.get("access_code"), "reference": data.get("reference", reference)}

    async def verify_transaction(self, reference: str) -> dict[str, Any] | None:
        try:
            return await self._request("GET", f"/transaction/verify/{reference}")
        except PaystackError as exc:
            if exc.status_code == 404 or "not found" in exc.message.lower():
                return None
            raise

    async def create_customer(self, *, email, first_name, last_name, phone) -> str:
        body = {"email": email, "first_name": first_name, "last_name": last_name}
        if phone:
            body["phone"] = phone
        data = await self._request("POST", "/customer", json_body=body)
        return data["customer_code"]

    async def create_dedicated_account(self, customer_code: str) -> dict[str, Any]:
        data = await self._request(
            "POST", "/dedicated_account", json_body={"customer": customer_code, "preferred_bank": settings.PAYSTACK_DVA_PREFERRED_BANK}
        )
        return {
            "account_number": data["account_number"],
            "account_name": data.get("account_name"),
            "bank_name": (data.get("bank") or {}).get("name"),
        }

    async def bulk_transfer(self, transfers: list[dict[str, Any]]) -> list[TransferResult]:
        data = await self._request("POST", "/transfer/bulk", json_body={"currency": "NGN", "source": "balance", "transfers": transfers})
        results = []
        for row in data or []:
            results.append(TransferResult(reference=row.get("reference"), transfer_code=row.get("transfer_code"), status=str(row.get("status", "pending")).lower()))
        return results

    async def verify_transfer(self, reference: str) -> TransferResult | None:
        try:
            data = await self._request("GET", f"/transfer/verify/{reference}")
        except PaystackError as exc:
            if exc.status_code == 404 or "not found" in exc.message.lower():
                return None
            raise
        return TransferResult(
            reference=data.get("reference", reference),
            transfer_code=data.get("transfer_code"),
            status=str(data.get("status", "pending")).lower(),
            reason=data.get("reason") or data.get("gateway_response"),
        )

    async def get_balance(self) -> int:
        data = await self._request("GET", "/balance")
        for row in data or []:
            if row.get("currency") == "NGN":
                return int(row.get("balance", 0))
        return 0

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not signature or not self._secret:
            return False
        expected = hmac.new(self._secret.encode(), body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Fake provider for development & tests
# ---------------------------------------------------------------------------

FALLBACK_BANKS = [
    {"name": "Access Bank", "code": "044"},
    {"name": "Citibank Nigeria", "code": "023"},
    {"name": "Ecobank Nigeria", "code": "050"},
    {"name": "Fidelity Bank", "code": "070"},
    {"name": "First Bank of Nigeria", "code": "011"},
    {"name": "First City Monument Bank", "code": "214"},
    {"name": "Globus Bank", "code": "00103"},
    {"name": "Guaranty Trust Bank", "code": "058"},
    {"name": "Jaiz Bank", "code": "301"},
    {"name": "Keystone Bank", "code": "082"},
    {"name": "Kuda Bank", "code": "50211"},
    {"name": "Moniepoint MFB", "code": "50515"},
    {"name": "OPay Digital Services", "code": "999992"},
    {"name": "PalmPay", "code": "999991"},
    {"name": "Polaris Bank", "code": "076"},
    {"name": "Providus Bank", "code": "101"},
    {"name": "Stanbic IBTC Bank", "code": "221"},
    {"name": "Sterling Bank", "code": "232"},
    {"name": "Union Bank of Nigeria", "code": "032"},
    {"name": "United Bank For Africa", "code": "033"},
    {"name": "Unity Bank", "code": "215"},
    {"name": "Wema Bank", "code": "035"},
    {"name": "Zenith Bank", "code": "057"},
]

_FAKE_FIRST = ["ADAEZE", "CHINEDU", "FUNMILAYO", "IBRAHIM", "NGOZI", "OLUWASEUN", "TUNDE", "AMAKA", "EMEKA", "HALIMA", "KELECHI", "YETUNDE"]
_FAKE_LAST = ["OKAFOR", "ADEYEMI", "BELLO", "EZE", "OKONKWO", "BALOGUN", "USMAN", "NWOSU", "ABUBAKAR", "OYELARAN"]


class FakePaystack:
    """Deterministic simulation. Account numbers ending in ``13`` fail transfers,
    account numbers starting with ``000`` can't be resolved."""

    name = "fake"
    WEBHOOK_SECRET = "fake-webhook-secret"

    def _key(self, *parts: str) -> str:
        return k("fake", *parts)

    async def list_banks(self) -> list[dict[str, Any]]:
        return [dict(b) for b in FALLBACK_BANKS]

    async def resolve_account(self, account_number: str, bank_code: str) -> str:
        if not account_number.isdigit() or len(account_number) != 10 or account_number.startswith("000"):
            raise PaystackError("Could not resolve account name. Check the account number and bank.", status_code=422)
        if bank_code not in {b["code"] for b in FALLBACK_BANKS}:
            raise PaystackError("Unknown bank code.", status_code=422)
        override = await redis.get(self._key("name", account_number))
        if override:
            return override
        rng = random.Random(int(account_number))
        return f"{rng.choice(_FAKE_FIRST)} {rng.choice(_FAKE_LAST)}"

    async def set_account_name(self, account_number: str, name: str) -> None:
        """Test helper: make an account resolve to a specific name."""
        await redis.set(self._key("name", account_number), name.upper(), ex=86400)

    async def create_recipient(self, name: str, account_number: str, bank_code: str) -> str:
        code = "RCP_" + hashlib.sha1(f"{bank_code}:{account_number}".encode()).hexdigest()[:14]
        await self.remember_recipient(code, account_number)
        return code

    async def initialize_transaction(self, *, email, amount_kobo, reference, callback_url, metadata, channels) -> dict[str, Any]:
        record = {"reference": reference, "amount": amount_kobo, "status": "pending", "metadata": metadata, "email": email, "callback_url": callback_url}
        await redis.set(self._key("txn", reference), json.dumps(record), ex=7 * 86400)
        url = f"{settings.FRONTEND_URL}/dev/checkout?reference={reference}"
        return {"authorization_url": url, "access_code": "fake_" + reference[-8:], "reference": reference}

    async def complete_transaction(self, reference: str, fees_kobo: int | None = None, channel: str = "card") -> dict[str, Any] | None:
        raw = await redis.get(self._key("txn", reference))
        if not raw:
            return None
        record = json.loads(raw)
        record["status"] = "success"
        record["channel"] = channel
        record["fees"] = fees_kobo
        await redis.set(self._key("txn", reference), json.dumps(record), ex=7 * 86400)
        return record

    async def verify_transaction(self, reference: str) -> dict[str, Any] | None:
        raw = await redis.get(self._key("txn", reference))
        if not raw:
            return None
        record = json.loads(raw)
        return {
            "reference": reference,
            "status": record["status"] if record["status"] == "success" else "abandoned",
            "amount": record["amount"],
            "fees": record.get("fees"),
            "channel": record.get("channel", "card"),
            "paid_at": None,
            "metadata": record.get("metadata"),
            "gateway_response": "Approved" if record["status"] == "success" else "Pending",
        }

    async def create_customer(self, *, email, first_name, last_name, phone) -> str:
        return "CUS_" + hashlib.sha1(email.encode()).hexdigest()[:12]

    async def create_dedicated_account(self, customer_code: str) -> dict[str, Any]:
        digits = str(int(hashlib.sha1(customer_code.encode()).hexdigest(), 16))[-8:]
        return {"account_number": "99" + digits, "account_name": "STREIXPEI / WORKGROUP", "bank_name": "Test Bank (simulated)"}

    async def bulk_transfer(self, transfers: list[dict[str, Any]]) -> list[TransferResult]:
        results = []
        for transfer in transfers:
            account = await redis.get(self._key("rcp", transfer["recipient"])) or ""
            status = "failed" if account.endswith("13") else "success"
            result = TransferResult(
                reference=transfer["reference"],
                transfer_code="TRF_" + transfer["reference"][-10:],
                status=status,
                reason="Account could not be credited (simulated)" if status == "failed" else None,
            )
            await redis.set(self._key("trf", transfer["reference"]), json.dumps(result.__dict__), ex=7 * 86400)
            results.append(result)
        return results

    async def remember_recipient(self, recipient_code: str, account_number: str) -> None:
        await redis.set(self._key("rcp", recipient_code), account_number, ex=30 * 86400)

    async def verify_transfer(self, reference: str) -> TransferResult | None:
        raw = await redis.get(self._key("trf", reference))
        if not raw:
            return None
        return TransferResult(**json.loads(raw))

    async def get_balance(self) -> int:
        return 10_000_000_000_00

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        expected = hmac.new(self.WEBHOOK_SECRET.encode(), body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature)


_provider: PaymentsProvider | None = None


def get_provider() -> PaymentsProvider:
    global _provider
    if _provider is None:
        if settings.PAYMENTS_PROVIDER == "fake":
            _provider = FakePaystack()
        else:
            _provider = PaystackClient(settings.PAYSTACK_SECRET_KEY, settings.PAYSTACK_BASE_URL, settings.PAYSTACK_TIMEOUT_SECONDS)
    return _provider


def set_provider(provider: PaymentsProvider | None) -> None:
    """Used by tests to inject a provider."""
    global _provider
    _provider = provider
