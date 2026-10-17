"""Streixpei API — payroll operations for Nigerian businesses."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from .api.v1 import admin, ai, auth, dev, money, public, staff, users, workgroups
from .core.config import settings
from .core.database import SessionLocal, engine
from .core.errors import register_error_handlers
from .core.redis import redis, redis_lock
from .services import billing, scheduler
from .services.auth import ensure_admin

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("streixpei")
logging.getLogger("apscheduler").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Several workers may start at once: only one seeds, the rest skip.
    async with redis_lock("startup-seed", ttl_seconds=60) as acquired:
        if acquired:
            async with SessionLocal() as session:
                await billing.seed_plans(session)
                await session.commit()
                await ensure_admin(session)
    if settings.SCHEDULER_ENABLED and settings.ENVIRONMENT != "test":
        scheduler.start()
    logger.info("%s API ready (%s, payments=%s, ai=%s)", settings.APP_NAME, settings.ENVIRONMENT, settings.PAYMENTS_PROVIDER,
                "claude" if settings.ai_configured else "basic")
    yield
    scheduler.stop()
    await engine.dispose()
    await redis.aclose()


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="2.0.0",
    description="Workgroups, staff onboarding without accounts, wallet funding through Paystack, payroll disbursement and the SPI assistant.",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

register_error_handlers(app)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
    max_age=600,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    if request.url.path.startswith("/api/") and request.method != "GET" or elapsed > 1500:
        logger.info("%s %s %s %.0fms rid=%s", request.method, request.url.path, response.status_code, elapsed, request_id)
    return response


API = "/api/v1"
for module in (auth, users, workgroups, staff, money, public, ai, admin):
    app.include_router(module.router, prefix=API)
if settings.PAYMENTS_PROVIDER == "fake" and not settings.is_production:
    app.include_router(dev.router, prefix=API)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    status = {"api": "ok"}
    try:
        async with SessionLocal() as session:
            await session.execute(text("select 1"))
        status["database"] = "ok"
    except Exception:
        status["database"] = "down"
    try:
        await redis.ping()
        status["redis"] = "ok"
    except Exception:
        status["redis"] = "down"
    return status


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"name": f"{settings.APP_NAME} API", "status": "ok"}
