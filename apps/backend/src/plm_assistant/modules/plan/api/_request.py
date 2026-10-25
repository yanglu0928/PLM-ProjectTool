"""Strict bounded JSON and canonical identity parsing for Plan HTTP."""

from __future__ import annotations

import json
import uuid

from fastapi import Request

from plm_assistant.modules.platform.application.errors import ApplicationError


_MAX_BODY = 128 * 1024


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def read_body(request: Request, headers: tuple[tuple[bytes, bytes], ...], *,
                    maximum_bytes: int = _MAX_BODY) -> object:
    if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 32 * 1024 * 1024:
        raise ValueError("invalid bounded Plan request limit")
    values = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(values) != 1 or values[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > maximum_bytes:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(raw.decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


def canonical_uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed
