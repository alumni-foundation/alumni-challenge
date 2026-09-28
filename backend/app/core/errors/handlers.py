from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors.exceptions import AppError

logger = structlog.get_logger("errors")


def _error_body(code: str, message: str, details: object = None) -> dict[str, Any]:
    """
    Standard error envelope. Every error response from this API has
    this exact shape — frontends and mobile clients can rely on it.
    """
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def _safe_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """
    Pydantic's raw error dicts include `input` (the submitted value — for
    a registration request that is the user's password) and `ctx` (which
    can hold non-JSON-serializable exception objects). Return only the
    fields a client actually needs: where, what, and which rule.
    """
    return [
        {"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.exception("unhandled_app_error", code=exc.code, path=request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "validation_error", "Request validation failed", details=_safe_errors(exc)
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals to the client. Full detail goes to logs/Sentry only.
        logger.exception("unhandled_exception", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "Something went wrong on our end."),
        )
