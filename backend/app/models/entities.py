"""All database tables.

Money is always stored as integer kobo (BigInteger). Never floats.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base, utcnow as _now
from .base import Timestamps, UUIDPk

# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="manager")  # manager | admin
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active | suspended | deleted
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    workgroups: Mapped[list["Workgroup"]] = relationship(back_populates="owner", lazy="noload")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_verified(self) -> bool:
        return self.email_verified_at is not None


# --------------------------------------------------------------------------
# Workgroups
# --------------------------------------------------------------------------


class Workgroup(UUIDPk, Timestamps, Base):
    __tablename__ = "workgroups"
    __table_args__ = (
        CheckConstraint("headcount >= 1", name="headcount_positive"),
        CheckConstraint("wallet_balance_kobo >= 0", name="wallet_non_negative"),
        CheckConstraint("payday_day BETWEEN 1 AND 31", name="payday_day_range"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active | archived
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_id_prefix: Mapped[str] = mapped_column(String(6), nullable=False)

    invite_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    invite_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    invite_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    payment_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")  # manual | automatic
    payday_day: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    payday_time: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Lagos")
    next_payday_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_reminder_key: Mapped[str | None] = mapped_column(String(20))

    wallet_balance_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    paystack_customer_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    dva_account_number: Mapped[str | None] = mapped_column(String(20))
    dva_account_name: Mapped[str | None] = mapped_column(String(160))
    dva_bank_name: Mapped[str | None] = mapped_column(String(120))

    owner: Mapped[User] = relationship(back_populates="workgroups", lazy="joined")
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="workgroup", uselist=False, lazy="joined", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------
# Staff
# --------------------------------------------------------------------------


class Role(UUIDPk, Timestamps, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("workgroup_id", "name_norm"),)

    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_norm: Mapped[str] = mapped_column(String(80), nullable=False)
    salary_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(255))


class StaffMember(UUIDPk, Timestamps, Base):
    """A seat in a workgroup, keyed by its staff ID.

    The row exists from the moment the staff ID is generated or uploaded
    (status ``pending``). When the staff member completes the onboarding form
    with that ID the row becomes ``registered``. ``(workgroup_id,
    staff_code_norm)`` is the natural key: one ID belongs to exactly one staff
    member.
    """

    __tablename__ = "staff_members"
    __table_args__ = (
        UniqueConstraint("workgroup_id", "staff_code_norm"),
        CheckConstraint("salary_kobo IS NULL OR salary_kobo >= 0", name="salary_non_negative"),
        Index("ix_staff_members_workgroup_status", "workgroup_id", "status"),
    )

    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False)
    staff_code: Mapped[str] = mapped_column(String(40), nullable=False)
    staff_code_norm: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # generated | uploaded | manual
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | registered | inactive

    preset_name: Mapped[str | None] = mapped_column(String(160))  # name supplied with an uploaded list
    first_name: Mapped[str | None] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))

    role_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("roles.id", ondelete="SET NULL"), index=True)
    salary_kobo: Mapped[int | None] = mapped_column(BigInteger)  # overrides role salary when set

    bank_code: Mapped[str | None] = mapped_column(String(20))
    bank_name: Mapped[str | None] = mapped_column(String(120))
    account_number: Mapped[str | None] = mapped_column(String(20))
    account_name: Mapped[str | None] = mapped_column(String(160))
    name_match: Mapped[bool | None] = mapped_column(Boolean)
    bank_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paystack_recipient_code: Mapped[str | None] = mapped_column(String(64))

    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_ip: Mapped[str | None] = mapped_column(String(64))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role | None] = relationship(lazy="joined")

    @property
    def display_name(self) -> str:
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}".strip()
        return self.preset_name or ""

    @property
    def effective_salary_kobo(self) -> int:
        if self.salary_kobo is not None:
            return self.salary_kobo
        if self.role is not None:
            return self.role.salary_kobo
        return 0

    @property
    def payout_ready(self) -> bool:
        return (
            self.status == "registered"
            and bool(self.paystack_recipient_code)
            and self.bank_verified_at is not None
            and self.effective_salary_kobo > 0
        )


# --------------------------------------------------------------------------
# Billing
# --------------------------------------------------------------------------


class Plan(Timestamps, Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(160))
    min_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    max_staff: Mapped[int | None] = mapped_column(Integer)
    base_fee_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    per_staff_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ai_monthly_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    features: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Subscription(UUIDPk, Timestamps, Base):
    __tablename__ = "subscriptions"

    workgroup_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plan_code: Mapped[str] = mapped_column(String(20), ForeignKey("plans.code"), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")  # monthly | annual
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="trialing")
    # trialing | active | past_due | expired | canceled
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_notice_key: Mapped[str | None] = mapped_column(String(40))

    workgroup: Mapped[Workgroup] = relationship(back_populates="subscription", lazy="noload")
    plan: Mapped[Plan] = relationship(lazy="joined")


class Invoice(UUIDPk, Timestamps, Base):
    __tablename__ = "invoices"

    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # subscription | renewal | seats
    plan_code: Mapped[str] = mapped_column(String(20), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_seats: Mapped[int | None] = mapped_column(Integer)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | paid | void
    paid_via: Mapped[str | None] = mapped_column(String(20))  # wallet | checkout
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(String(255))


# --------------------------------------------------------------------------
# Money in: payments collected through Paystack
# --------------------------------------------------------------------------


class Payment(UUIDPk, Timestamps, Base):
    __tablename__ = "payments"

    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)  # wallet | payroll | invoice
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # checkout | transfer | dva
    reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)  # gross charged to the payer
    expected_net_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_estimate_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    fees_kobo: Mapped[int | None] = mapped_column(BigInteger)
    net_kobo: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | success | failed | abandoned
    authorization_url: Mapped[str | None] = mapped_column(Text)
    access_code: Mapped[str | None] = mapped_column(String(64))
    payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("payroll_runs.id", ondelete="SET NULL"), index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="SET NULL"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_channel: Mapped[str | None] = mapped_column(String(40))
    raw: Mapped[dict | None] = mapped_column(JSONB)


# --------------------------------------------------------------------------
# Wallet ledger
# --------------------------------------------------------------------------


class WalletEntry(UUIDPk, Base):
    __tablename__ = "wallet_entries"
    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="amount_positive"),
        CheckConstraint("direction IN ('credit','debit')", name="direction_valid"),
        Index("ix_wallet_entries_workgroup_created", "workgroup_id", "created_at"),
        Index(
            "uq_wallet_entries_type_reference",
            "entry_type",
            "reference",
            unique=True,
            postgresql_where=text("reference IS NOT NULL"),
        ),
    )

    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # funding | payroll | transfer_fees | commission | refund | subscription | adjustment
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("payroll_runs.id", ondelete="SET NULL"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("payments.id", ondelete="SET NULL"))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class Withdrawal(UUIDPk, Timestamps, Base):
    """Money the manager sends from the wallet back to a bank account."""

    __tablename__ = "withdrawals"
    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="amount_positive"),
        Index("ix_withdrawals_status_updated", "status", "updated_at"),
    )

    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bank_code: Mapped[str] = mapped_column(String(12), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    transfer_code: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    # queued | processing | success | failed | reversed
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    needs_verification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------------
# Payroll
# --------------------------------------------------------------------------


class PayrollRun(UUIDPk, Timestamps, Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        Index(
            "uq_payroll_runs_automatic_period",
            "workgroup_id",
            "period_key",
            unique=True,
            postgresql_where=text("trigger = 'automatic' AND status <> 'canceled'"),
        ),
    )

    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")  # manual | automatic | assistant | retry
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    # draft | awaiting_funding | ready | processing | completed | partially_failed | failed | canceled
    period_key: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    period_label: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    staff_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    salaries_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    transfer_fees_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    commission_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refunded_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    funded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disbursed_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(255))

    items: Mapped[list["PayrollItem"]] = relationship(
        back_populates="run", lazy="noload", cascade="all, delete-orphan", order_by="PayrollItem.staff_name"
    )


class PayrollItem(UUIDPk, Timestamps, Base):
    __tablename__ = "payroll_items"
    __table_args__ = (
        UniqueConstraint("run_id", "staff_id"),
        CheckConstraint("amount_kobo > 0", name="amount_positive"),
        Index("ix_payroll_items_status_updated", "status", "updated_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("staff_members.id", ondelete="SET NULL"), index=True)
    staff_code: Mapped[str] = mapped_column(String(40), nullable=False)
    staff_name: Mapped[str] = mapped_column(String(160), nullable=False)
    staff_email: Mapped[str | None] = mapped_column(String(255))
    role_name: Mapped[str | None] = mapped_column(String(80))
    bank_name: Mapped[str | None] = mapped_column(String(120))
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(160))
    recipient_code: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    commission_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending | queued | processing | success | failed | reversed
    reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    transfer_code: Mapped[str | None] = mapped_column(String(64))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    needs_verification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receipt_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    run: Mapped[PayrollRun] = relationship(back_populates="items", lazy="noload")


# --------------------------------------------------------------------------
# Platform: settings, notifications, audit, outbox, webhooks, AI
# --------------------------------------------------------------------------


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | int | str | float | bool | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Notification(UUIDPk, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workgroup_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="info")  # info | success | warning | danger
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(255))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_workgroup_created", "workgroup_id", "created_at"),)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    actor_label: Mapped[str] = mapped_column(String(160), nullable=False)
    workgroup_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class OutboxEmail(UUIDPk, Base):
    __tablename__ = "outbox_emails"
    __table_args__ = (Index("ix_outbox_emails_status_next", "status", "next_attempt_at"),)

    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | sent | failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class WebhookEvent(UUIDPk, Base):
    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    event_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AIMessage(UUIDPk, Base):
    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_conversation_created", "conversation_id", "created_at"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workgroup_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12), nullable=False)  # user | assistant
    content: Mapped[list] = mapped_column(JSONB, nullable=False)
    visible_text: Mapped[str | None] = mapped_column(Text)
    counts_toward_quota: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class AIAction(UUIDPk, Base):
    __tablename__ = "ai_actions"

    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workgroup_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False)
    tool: Mapped[str] = mapped_column(String(60), nullable=False)
    args: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    requires_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | executed | canceled | failed | expired
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
