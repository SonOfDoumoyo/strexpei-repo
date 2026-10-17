"""Transactional email.

Emails are rendered immediately and written to the ``outbox_emails`` table in
the same database transaction as the action that caused them. A background
job delivers them over SMTP (Gmail by default) with exponential back-off, so
no email is lost when SMTP hiccups or the server restarts.
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Any

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.money import format_naira
from ..core.timeutil import get_tz, utcnow
from ..models import OutboxEmail

logger = logging.getLogger("streixpei.mail")

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["naira"] = lambda kobo: format_naira(int(kobo or 0))


def _local_datetime(value: datetime | None, fmt: str = "%d %b %Y, %I:%M %p") -> str:
    if value is None:
        return ""
    return value.astimezone(get_tz(settings.TIMEZONE)).strftime(fmt)


_env.filters["localdt"] = _local_datetime
_env.filters["localdate"] = lambda value: _local_datetime(value, "%d %B %Y")

SUBJECTS: dict[str, str] = {
    "verify_email": "Confirm your email address",
    "welcome": "Welcome to {app_name}",
    "password_reset": "Your {app_name} password reset code",
    "password_changed": "Your {app_name} password was changed",
    "staff_welcome": "You've been added to {company} payroll",
    "staff_invite": "{company} invites you to join its payroll on {app_name}",
    "all_staff_registered": "Every staff member in {company} has registered",
    "funding_received": "Funds received: {amount} for {company}",
    "payroll_funded": "Payroll {run_number} is funded and ready to disburse",
    "payroll_completed": "Payroll {run_number} for {company}: {outcome}",
    "payslip": "Salary payment from {company} — {period}",
    "payroll_shortfall": "Action needed: fund {company} payroll for {period}",
    "payday_reminder": "Payday for {company} is {when}",
    "invoice_paid": "Receipt for invoice {invoice_number}",
    "subscription_notice": "{headline}",
    "admin_alert": "[{app_name} admin] {title}",
    "withdrawal_update": "{headline}",
}


def _html_to_text(markup: str) -> str:
    text = re.sub(r"(?is)<(style|head|script)[^>]*>.*?</\1>", "", markup)
    text = re.sub(r'(?is)<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: f"{re.sub('<[^>]+>', '', m.group(2)).strip()} ({m.group(1)})", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|h[1-6]|tr|li|table)>", "\n", text)
    text = re.sub(r"(?i)</t[dh]>", "  ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip() + "\n"


def mask_account(number: str | None) -> str:
    if not number:
        return ""
    return "••••" + number[-4:]


def render(template: str, context: dict[str, Any]) -> tuple[str, str, str]:
    base = {
        "app_name": settings.APP_NAME,
        "company_name": settings.COMPANY_NAME,
        "frontend_url": settings.FRONTEND_URL,
        "support_email": settings.SUPPORT_EMAIL,
        "year": utcnow().astimezone(get_tz(settings.TIMEZONE)).year,
    }
    ctx = {**base, **context}
    subject_tpl = SUBJECTS[template]
    subject = subject_tpl.format(**{k: v for k, v in ctx.items() if isinstance(v, (str, int))})
    ctx.setdefault("subject", subject)
    html = _env.get_template(f"{template}.html").render(**ctx)
    return subject, html, _html_to_text(html)


def queue_email(session: AsyncSession, to: str | None, template: str, context: dict[str, Any]) -> OutboxEmail | None:
    if not to:
        return None
    subject, html, text = render(template, context)
    email = OutboxEmail(to_email=to, subject=subject, html=html, text_body=text, template=template)
    session.add(email)
    return email


async def _send_smtp(message: EmailMessage) -> None:
    await aiosmtplib.send(
        message,
        hostname=settings.MAIL_SERVER,
        port=settings.MAIL_PORT,
        username=settings.MAIL_USERNAME,
        password=settings.MAIL_PASSWORD,
        start_tls=settings.MAIL_STARTTLS and not settings.MAIL_SSL_TLS,
        use_tls=settings.MAIL_SSL_TLS,
        timeout=settings.MAIL_TIMEOUT_SECONDS,
    )


def build_message(row: OutboxEmail) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((settings.MAIL_FROM_NAME, settings.mail_from))
    message["To"] = row.to_email
    message["Subject"] = row.subject
    message["Reply-To"] = settings.SUPPORT_EMAIL
    domain = settings.mail_from.split("@")[-1] if "@" in settings.mail_from else "streixpei.local"
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(row.text_body)
    message.add_alternative(row.html, subtype="html")
    return message


MAX_ATTEMPTS = 8


async def deliver_pending(session: AsyncSession, batch_size: int = 25) -> int:
    """Send due emails. Returns the number delivered."""
    now = utcnow()
    rows = (
        (
            await session.execute(
                select(OutboxEmail)
                .where(OutboxEmail.status == "pending", OutboxEmail.next_attempt_at <= now)
                .order_by(OutboxEmail.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    sent = 0
    for row in rows:
        row.attempts += 1
        try:
            if settings.mail_configured:
                await _send_smtp(build_message(row))
            else:
                logger.info("MAIL (not configured, logged only) to=%s subject=%s", row.to_email, row.subject)
            row.status = "sent"
            row.sent_at = utcnow()
            row.last_error = None
            sent += 1
        except Exception as exc:  # network/SMTP errors
            row.last_error = f"{exc.__class__.__name__}: {exc}"[:1000]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "failed"
                logger.error("Email to %s permanently failed: %s", row.to_email, row.last_error)
            else:
                row.next_attempt_at = utcnow() + timedelta(seconds=min(3600, 30 * 2 ** (row.attempts - 1)))
                logger.warning("Email to %s failed (attempt %s): %s", row.to_email, row.attempts, row.last_error)
    await session.commit()
    return sent


async def retry_failed(session: AsyncSession) -> int:
    result = await session.execute(
        update(OutboxEmail).where(or_(OutboxEmail.status == "failed")).values(status="pending", attempts=0, next_attempt_at=utcnow())
    )
    await session.commit()
    return result.rowcount or 0
