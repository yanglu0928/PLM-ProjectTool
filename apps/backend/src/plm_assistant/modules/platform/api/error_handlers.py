from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from plm_assistant.modules.platform.application.errors import (
    COMMON_ERRORS,
    ApplicationError,
    ErrorSpec,
)
from plm_assistant.modules.platform.application.trace_context import (
    is_canonical_uuid,
    new_uuid7 as _new_uuid7,
)


def error_trace_id(request: Request) -> str:
    """Use the request context, with a safe fallback for isolated handlers."""

    attached = getattr(request.state, "trace_id", None)
    if is_canonical_uuid(attached):
        return attached
    supplied = request.headers.get("x-trace-id", "")
    if is_canonical_uuid(supplied):
        return supplied
    return _new_uuid7()


def _response(
    request: Request, spec: ErrorSpec, *, trace_id: str | None = None
) -> JSONResponse:
    trace_id = trace_id or error_trace_id(request)
    return JSONResponse(
        status_code=spec.status_code,
        content={
            "error": {"code": spec.code, "message": spec.message, "details": []},
            "trace_id": trace_id,
        },
        headers={"X-Trace-Id": trace_id, "Cache-Control": "no-store"},
    )


def _http_code(status_code: int) -> str:
    # A bare 403 must not reveal whether a project resource exists. Specific
    # CSRF or License failures use ApplicationError after their own checks.
    mapping = {
        400: "REQUEST_MALFORMED",
        401: "AUTH_REQUIRED",
        403: "RESOURCE_NOT_FOUND",
        404: "RESOURCE_NOT_FOUND",
        405: "REQUEST_METHOD_NOT_ALLOWED",
        409: "CONFLICT_STATE",
        413: "FILE_TOO_LARGE",
        415: "FILE_TYPE_UNSUPPORTED",
        422: "VALIDATION_FAILED",
        428: "CONFLICT_VERSION_REQUIRED",
        429: "AUTH_RATE_LIMITED",
        503: "SYSTEM_UNAVAILABLE",
    }
    return mapping.get(status_code, "SYSTEM_INTERNAL")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        return _response(request, exc.spec)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        malformed_json = any(
            item.get("type") == "json_invalid" for item in exc.errors()
        )
        # Pydantic's raw input and model paths are not public.
        code = "REQUEST_MALFORMED" if malformed_json else "VALIDATION_FAILED"
        return _response(request, COMMON_ERRORS[code])

    @app.exception_handler(StarletteHTTPException)
    async def http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _response(request, COMMON_ERRORS[_http_code(exc.status_code)])

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        del exc  # Raw exception text and traceback must never enter generic logs.
        trace_id = error_trace_id(request)
        try:
            request.app.state.loggers.application(
                event="request_failed",
                component="platform.api",
                level="ERROR",
                trace_id=trace_id,
                error_code="SYSTEM_INTERNAL",
            )
        except Exception:
            pass  # Logging failure must not turn a safe error into an unsafe one.
        return _response(request, COMMON_ERRORS["SYSTEM_INTERNAL"], trace_id=trace_id)
