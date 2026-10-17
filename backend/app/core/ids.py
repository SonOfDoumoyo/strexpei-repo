"""Identifier generation: staff IDs, invite codes, payment references."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone

# Crockford base32 without I, L, O, U: nothing a staff member can misread.
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
INVITE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

STAFF_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-/.]{0,39}$")


def random_block(length: int, alphabet: str = CROCKFORD) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(length))


def prefix_from_name(name: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", name).upper()
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    if len(words) >= 3:
        initials = "".join(w[0] for w in words if w[0].isalpha()).upper()[:3]
        if len(initials) == 3:
            return initials
    return (letters + "XXX")[:3]


def generate_staff_code(prefix: str) -> str:
    """e.g. ACM-7K3M-Q9TD (40 bits of randomness)."""
    return f"{prefix}-{random_block(4)}-{random_block(4)}"


def normalise_staff_code(code: str) -> str:
    return re.sub(r"\s+", " ", code.strip()).upper()


def is_valid_staff_code(code: str) -> bool:
    return bool(STAFF_CODE_PATTERN.match(code.strip()))


def generate_invite_code() -> str:
    return random_block(12, INVITE_ALPHABET)


def payment_reference(kind: str) -> str:
    """Paystack-safe reference: lowercase alphanumerics and dashes, 16-50 chars."""
    return f"spx-{kind}-{uuid.uuid4().hex}"


def transfer_reference() -> str:
    return f"spxt-{uuid.uuid4().hex}"


WITHDRAWAL_PREFIX = "spxw-"


def withdrawal_reference() -> str:
    return f"{WITHDRAWAL_PREFIX}{uuid.uuid4().hex}"


def human_number(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%y%m")
    return f"{prefix}-{stamp}-{random_block(6)}"
