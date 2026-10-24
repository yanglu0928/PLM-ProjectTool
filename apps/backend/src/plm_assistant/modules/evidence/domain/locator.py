"""Backward-compatible Evidence name for Document-owned typed positions."""

from __future__ import annotations

from plm_assistant.modules.document.domain.content_locator import (
    ContentLocatorError,
    validate_content_locator,
)


class EvidenceLocatorError(ValueError):
    """The locator is not a supported, reproducible typed position."""


def validate_evidence_locator(raw: object) -> dict[str, object]:
    try:
        return validate_content_locator(raw)
    except ContentLocatorError as error:
        raise EvidenceLocatorError(str(error)) from None
