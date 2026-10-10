"""Deployment username canonicalization, independent of database collation."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


class UsernameValidationError(ValueError):
    """Fixed-message validation failure; never echo the submitted name."""


@dataclass(frozen=True, slots=True)
class CanonicalUsername:
    display: str
    normalized: str


def normalize_username(value: str) -> CanonicalUsername:
    if type(value) is not str:
        raise UsernameValidationError("invalid username")
    display = unicodedata.normalize("NFC", value.strip())
    if (
        not display or len(display) > 255
        or any(unicodedata.category(char).startswith("C") for char in display)
    ):
        raise UsernameValidationError("invalid username")
    normalized = unicodedata.normalize("NFC", display.casefold())
    if not normalized or len(normalized) > 128:
        raise UsernameValidationError("invalid username")
    return CanonicalUsername(display=display, normalized=normalized)
