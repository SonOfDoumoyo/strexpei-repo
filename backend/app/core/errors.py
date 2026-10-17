"""Consistent error responses.

Every error leaves the API as::

    {"error": {"code": "...", "message": "...", "details": {...}}, "detail": "..."}

``detail`` duplicates the message so generic HTTP clients still show something
sensible.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("streixpei.errors")


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be completed."

    def __init__(self, message: str | None = None, *, code: str | None = None, status_code: int | None = None, details: dict[str, Any] | None = None):
        self.message = message or self.message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "We couldn't find what you were looking for."


class Unauthorized(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Please sign in to continue."


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You don't have permission to do that."


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "That conflicts with existing data."


class ValidationFailed(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"
    message = "Some of the information provided isn't valid."


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many attempts. Please wait a moment and try again."


class PaymentRequired(AppError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "subscription_required"
    message = "An active subscription is required for this action."


class ProviderError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "provider_error"
    message = "Our payment partner is unavailable right now. Please try again shortly."


class InsufficientFunds(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "insufficient_funds"
    message = "The wallet balance is not enough for this action."


class ServiceUnavailable(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "This service is temporarily unavailable."


def _payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}, "detail": message}


def _humanise_validation(exc: RequestValidationError) -> tuple[str, dict[str, Any]]:
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        field = ".".join(loc) or "request"
        msg = str(err.get("msg", "Invalid value"))
        msg = msg.removeprefix("Value error, ")
        fields.setdefault(field, msg)
    if len(fields) == 1:
        field, msg = next(iter(fields.items()))
        label = field.replace("_", " ").split(".")[-1]
        message = f"{label.capitalize()}: {msg}" if field != "request" else msg
    else:
        message = "Please check the highlighted fields."
    return message, {"fields": fields}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_payload(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        message, details = _humanise_validation(exc)
        return JSONResponse(status_code=422, content=_payload("validation_error", message, details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=_payload(code, message), headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled error on %s %s (request_id=%s)", request.method, request.url.path, request_id)
        return JSONResponse(
            status_code=500,
            content=_payload(
                "internal_error",
                "Something went wrong on our side. Please try again.",
                {"request_id": request_id} if request_id else None,
            ),
        )
