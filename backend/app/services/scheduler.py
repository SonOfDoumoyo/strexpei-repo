"""Background jobs. Each job takes a Redis lock so running several API
workers never executes the same job twice at once."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..core.database import SessionLocal
from ..core.redis import redis_lock
from . import auth, billing, mailer, payments, payroll, withdrawals

logger = logging.getLogger("streixpei.jobs")

scheduler = AsyncIOScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120})


def _job(name: str, ttl: int, fn: Callable) -> Callable[[], Awaitable[None]]:
    async def runner() -> None:
        async with redis_lock(f"job:{name}", ttl_seconds=ttl) as acquired:
            if not acquired:
                return
            async with SessionLocal() as session:
                try:
                    result = await fn(session)
                    if result:
                        logger.info("job %s: %s", name, result)
                except Exception:
                    await session.rollback()
                    logger.exception("job %s failed", name)

    runner.__name__ = f"job_{name}"
    return runner


def start() -> None:
    scheduler.add_job(_job("outbox", 120, mailer.deliver_pending), "interval", seconds=20, id="outbox")
    scheduler.add_job(_job("paydays", 900, payroll.run_due_paydays), "interval", minutes=1, id="paydays")
    scheduler.add_job(_job("reconcile-transfers", 900, payroll.reconcile_transfers), "interval", minutes=5, id="reconcile-transfers")
    scheduler.add_job(_job("reconcile-payments", 600, payments.reconcile_pending), "interval", minutes=5, id="reconcile-payments")
    scheduler.add_job(_job("reconcile-withdrawals", 600, withdrawals.reconcile), "interval", minutes=5, id="reconcile-withdrawals")
    scheduler.add_job(_job("payday-reminders", 600, payroll.send_payday_reminders), "interval", minutes=30, id="payday-reminders")
    scheduler.add_job(_job("subscriptions", 900, billing.process_subscriptions), "interval", minutes=30, id="subscriptions")
    scheduler.add_job(_job("purge-users", 900, auth.purge_deleted_users), "cron", hour=2, minute=15, id="purge-users")
    scheduler.start()
    logger.info("Scheduler started with %s jobs", len(scheduler.get_jobs()))


def stop() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
