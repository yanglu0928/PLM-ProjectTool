"""Frozen UTC wire format for Auth Session expiration instants."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_session_instant(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware session instant required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
