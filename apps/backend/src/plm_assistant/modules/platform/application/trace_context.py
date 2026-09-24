from __future__ import annotations

import secrets
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


_CURRENT_TRACE_ID: ContextVar[str | None] = ContextVar(
    "plm_current_trace_id", default=None
)


def new_uuid7() -> str:
    """Generate a canonical UUIDv7 without a vendor package."""

    timestamp_ms = int(time.time_ns() // 1_000_000) & ((1 << 48) - 1)
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (
        (timestamp_ms << 80)
        | (7 << 76)
        | (random_a << 64)
        | (2 << 62)
        | random_b
    )
    return str(uuid.UUID(int=value))


def is_canonical_uuid(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def resolve_trace_id(value: object) -> str:
    if isinstance(value, str) and is_canonical_uuid(value):
        return value
    return new_uuid7()


def current_trace_id() -> str | None:
    """Read the current request or explicit worker trace."""

    return _CURRENT_TRACE_ID.get()


@contextmanager
def trace_scope(trace_id: str) -> Iterator[None]:
    """Bind a validated trace to an async task or explicit worker scope."""

    if not is_canonical_uuid(trace_id):
        raise ValueError("invalid trace id")
    token = _CURRENT_TRACE_ID.set(trace_id)
    try:
        yield
    finally:
        _CURRENT_TRACE_ID.reset(token)
