from __future__ import annotations

import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from plm_assistant.modules.platform.application.trace_context import (
    resolve_trace_id,
    trace_scope,
)
from plm_assistant.modules.platform.infrastructure.structured_logging import (
    StructuredLoggers,
)


class TraceMiddleware:
    """Bind one trace to an HTTP request and every response start."""

    def __init__(self, app: ASGIApp, *, loggers: StructuredLoggers) -> None:
        self.app = app
        self.loggers = loggers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"x-trace-id"
        ]
        try:
            candidate = supplied[0].decode("ascii") if len(supplied) == 1 else None
        except UnicodeDecodeError:
            candidate = None
        trace_id = resolve_trace_id(candidate)
        scope.setdefault("state", {})["trace_id"] = trace_id
        status_code: int | None = None
        started = time.monotonic_ns()

        async def send_with_trace(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Trace-Id"] = trace_id
            await send(message)

        with trace_scope(trace_id):
            await self.app(scope, receive, send_with_trace)
            if status_code is not None:
                try:
                    self.loggers.application(
                        event="request_completed",
                        component="platform.api",
                        trace_id=trace_id,
                        duration_ms=max(0, (time.monotonic_ns() - started) // 1_000_000),
                        status_code=status_code,
                    )
                except Exception:
                    pass  # Logging must not replace a completed response.
