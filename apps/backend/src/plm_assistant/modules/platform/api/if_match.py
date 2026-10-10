"""Strict strong-ETag precondition for versioned resource commands."""

from __future__ import annotations

import re

from plm_assistant.modules.platform.application.errors import ApplicationError


_STRONG_VERSION = re.compile(rb'"v(0|[1-9][0-9]{0,18})"\Z', re.ASCII)
_MAX_EXPECTED = 9_223_372_036_854_775_806


def parse_if_match(headers: tuple[tuple[bytes, bytes], ...]) -> int:
    """Return one record lock_version; never accept weak or multi-value tags."""
    try:
        matches = [value for name, value in headers if name.lower() == b"if-match"]
    except (AttributeError, TypeError):
        raise ApplicationError("REQUEST_MALFORMED") from None
    if not matches:
        raise ApplicationError("CONFLICT_VERSION_REQUIRED")
    if len(matches) != 1 or type(matches[0]) is not bytes:
        raise ApplicationError("REQUEST_MALFORMED")
    found = _STRONG_VERSION.fullmatch(matches[0])
    if found is None:
        raise ApplicationError("REQUEST_MALFORMED")
    version = int(found.group(1))
    if version > _MAX_EXPECTED:
        raise ApplicationError("REQUEST_MALFORMED")
    return version
