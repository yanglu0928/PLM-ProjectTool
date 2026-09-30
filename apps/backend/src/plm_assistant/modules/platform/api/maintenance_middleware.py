"""Optional ASGI write-window admission; production assembly is separate."""

from __future__ import annotations

from contextlib import AbstractContextManager
import re
from typing import Protocol

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from plm_assistant.modules.platform.application.errors import COMMON_ERRORS
from plm_assistant.modules.platform.application.trace_context import (
    is_canonical_uuid, new_uuid7,
)
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MaintenanceAdmissionError,
)


class MaintenanceAdmissionPort(Protocol):
    def admit(self) -> AbstractContextManager[object]: ...


_AUDITED_GET_CONTENT = tuple(re.compile(pattern) for pattern in (
    r"/api/v1/projects/[^/]+/documents/[^/]+/versions/[^/]+/content",
    r"/api/v1/global/documents/[^/]+/versions/[^/]+/content",
    r"/api/v1/projects/[^/]+/audit-exports/[^/]+/content",
    r"/api/v1/admin/audit-exports/[^/]+/content",
))


def _requires_admission(scope: Scope) -> bool:
    method = scope.get("method", "GET").upper()
    if method in ("HEAD", "OPTIONS"):
        return False
    if method == "GET":
        path = scope.get("path", "")
        return any(pattern.fullmatch(path) is not None
                   for pattern in _AUDITED_GET_CONTENT)
    return True


class MaintenanceAdmissionMiddleware:
    """Hold one admission across request body, response and Starlette background work."""

    def __init__(self, app: ASGIApp, *, admission: MaintenanceAdmissionPort) -> None:
        if admission is None:
            raise ValueError("maintenance admission required")
        self.app = app
        self.admission = admission

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _requires_admission(scope):
            await self.app(scope, receive, send)
            return
        response_started = False

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            with self.admission.admit():
                await self.app(scope, receive, tracked_send)
        except MaintenanceAdmissionError:
            # Once response bytes start, HTTP cannot be replaced; surface the
            # lost admission to the server rather than falsely reporting success.
            if response_started:
                raise
            trace_id = scope.setdefault("state", {}).get("trace_id")
            if not is_canonical_uuid(trace_id):
                trace_id = new_uuid7()
            spec = COMMON_ERRORS["SYSTEM_UNAVAILABLE"]
            response = JSONResponse(
                status_code=spec.status_code,
                content={"error": {"code": spec.code, "message": spec.message,
                                   "details": []}, "trace_id": trace_id},
                headers={"X-Trace-Id": trace_id, "Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
