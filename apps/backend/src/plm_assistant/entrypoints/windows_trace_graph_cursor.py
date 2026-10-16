"""Fail-closed current Windows account source for the Trace graph cursor key."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider
from plm_assistant.modules.trace.application.page_graph import TraceGraphCursorCodec


TRACE_GRAPH_CURSOR_KEY_REF = "trace-graph-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionTraceGraphCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Trace graph cursor key unavailable")


def create_windows_trace_graph_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> TraceGraphCursorCodec:
    try:
        source = WindowsSecretKeyProvider() if resolver is None else resolver
        return TraceGraphCursorCodec(source.resolve_key(TRACE_GRAPH_CURSOR_KEY_REF))
    except Exception:
        raise ProductionTraceGraphCursorStartupError() from None
