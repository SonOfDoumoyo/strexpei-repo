"""Request bodies. Money is always integer kobo."""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

NAME = Field(min_length=1, max_length=80)


class In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


def _phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    digits = re.sub(r"[\s\-()]", "", value)
    if not re.fullmatch(r"\+?\d{10,15}", digits):
        raise ValueError("Enter a valid phone number")
    return digits


def _password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Use at least 8 characters")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Use at least one letter and one number")
    return value


# ------------------------------------------------------------------ auth
class RegisterIn(In):
    first_name: str = NAME
    last_name: str = NAME
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(max_length=128)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _phone(v)
    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _password(v)


class LoginIn(In):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = True


class TokenIn(In):
    token: str = Field(min_length=10, max_length=600)


class EmailIn(In):
    email: EmailStr


class ResetPasswordIn(In):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")
    password: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _password(v)


class ProfileIn(In):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    phone: str | None = Field(default=None, max_length=20)
    preferences: dict | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _phone(v)


class ChangePasswordIn(In):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _password(v)


class PasswordIn(In):
    password: str = Field(min_length=1, max_length=128)


# ------------------------------------------------------------ workgroups
class WorkgroupCreateIn(In):
    name: str = Field(min_length=2, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=80)
    headcount: int = Field(ge=1, le=100_000)
    payment_mode: Literal["manual", "automatic"] = "manual"
    payday_day: int = Field(default=25, ge=1, le=31)
    payday_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class WorkgroupUpdateIn(In):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=80)
    payment_mode: Literal["manual", "automatic"] | None = None
    payday_day: int | None = Field(default=None, ge=1, le=31)
    payday_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    auto_renew: bool | None = None


class SeatsIn(In):
    seats: int = Field(ge=1, le=100_000)


class InviteToggleIn(In):
    active: bool


class InviteEmailIn(In):
    emails: list[EmailStr] = Field(min_length=1, max_length=200)
    message: str | None = Field(default=None, max_length=300)


# ------------------------------------------------------------------ staff
class GenerateIdsIn(In):
    count: int = Field(ge=1, le=5000)


class PasteIdsIn(In):
    text: str = Field(min_length=1, max_length=200_000)


class StaffUpdateIn(In):
    salary_kobo: int | None = Field(default=None, ge=0, le=100_000_000_00)
    role_id: uuid.UUID | None = None
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    status: Literal["active", "inactive"] | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _phone(v)


class BulkStaffIn(In):
    staff_ids: list[uuid.UUID] = Field(min_length=1, max_length=5000)
    salary_kobo: int | None = Field(default=None, ge=0, le=100_000_000_00)
    role_id: uuid.UUID | None = None
    clear_salary_override: bool = False


class BankIn(In):
    bank_code: str = Field(min_length=2, max_length=20)
    account_number: str = Field(pattern=r"^\d{10}$")


class StaffCreateIn(In):
    staff_code: str | None = Field(default=None, max_length=40)
    first_name: str = NAME
    last_name: str = NAME
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    bank_code: str = Field(min_length=2, max_length=20)
    account_number: str = Field(pattern=r"^\d{10}$")
    salary_kobo: int | None = Field(default=None, ge=0, le=100_000_000_00)
    role_id: uuid.UUID | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _phone(v)


class StaffIdsIn(In):
    staff_ids: list[uuid.UUID] | None = Field(default=None, max_length=5000)


class RoleIn(In):
    name: str = Field(min_length=1, max_length=80)
    salary_kobo: int = Field(ge=0, le=100_000_000_00)
    description: str | None = Field(default=None, max_length=255)


class RoleUpdateIn(In):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    salary_kobo: int | None = Field(default=None, ge=0, le=100_000_000_00)
    description: str | None = Field(default=None, max_length=255)


# ------------------------------------------------------------ public join
class JoinCheckIn(In):
    staff_code: str = Field(min_length=1, max_length=40)


class JoinResolveIn(In):
    staff_code: str = Field(min_length=1, max_length=40)
    bank_code: str = Field(min_length=2, max_length=20)
    account_number: str = Field(pattern=r"^\d{10}$")


class JoinRegisterIn(In):
    staff_code: str = Field(min_length=1, max_length=40)
    first_name: str = NAME
    last_name: str = NAME
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    bank_code: str = Field(min_length=2, max_length=20)
    account_number: str = Field(pattern=r"^\d{10}$")

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _phone(v)


# ------------------------------------------------------------------ money
class FundIn(In):
    amount_kobo: int = Field(ge=100_00, le=500_000_000_00)
    channel: Literal["checkout", "transfer"] = "checkout"


class WithdrawIn(In):
    amount_kobo: int = Field(ge=1_000_00, le=50_000_000_00)
    bank_code: str = Field(min_length=2, max_length=20)
    account_number: str = Field(pattern=r"^\d{10}$")
    password: str = Field(min_length=1, max_length=128)


class RunCreateIn(In):
    staff_ids: list[uuid.UUID] | None = Field(default=None, max_length=5000)
    note: str | None = Field(default=None, max_length=255)


class FundRunIn(In):
    channel: Literal["checkout", "transfer"] = "checkout"


class SubscribeIn(In):
    seats: int = Field(ge=1, le=100_000)
    billing_cycle: Literal["monthly", "annual"] = "monthly"
    pay_with: Literal["wallet", "checkout"] = "checkout"


class PayInvoiceIn(In):
    pay_with: Literal["wallet", "checkout"] = "checkout"


# --------------------------------------------------------------------- ai
class AIChatIn(In):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None
    workgroup_id: uuid.UUID | None = None


class AIActionIn(In):
    confirm: bool
    password: str | None = Field(default=None, max_length=128)


# ------------------------------------------------------------------ admin
class AdminUserIn(In):
    status: Literal["active", "suspended"]


class PlanUpdateIn(In):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    tagline: str | None = Field(default=None, max_length=160)
    min_staff: int | None = Field(default=None, ge=1)
    max_staff: int | None = Field(default=None, ge=1)
    unlimited: bool | None = None
    base_fee_kobo: int | None = Field(default=None, ge=0)
    per_staff_kobo: int | None = Field(default=None, ge=0)
    ai_monthly_quota: int | None = Field(default=None, ge=0)
    features: list[str] | None = None
    active: bool | None = None


class AdminSettingsIn(In):
    commission_bps: int | None = Field(default=None, ge=0, le=1000)
    trial_days: int | None = Field(default=None, ge=0, le=90)
    trial_ai_quota: int | None = Field(default=None, ge=0, le=10_000)
    annual_discount_months: int | None = Field(default=None, ge=0, le=6)
    grace_days: int | None = Field(default=None, ge=0, le=30)
    payday_reminder_days: int | None = Field(default=None, ge=1, le=14)
    fees: dict | None = None
