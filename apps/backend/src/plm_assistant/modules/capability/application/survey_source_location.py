"""Capability-owned public location target for an immutable Survey source."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CapabilityDocumentLocation:
    document_id: uuid.UUID
    document_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CapabilitySurveySourceLocation:
    baseline_id: uuid.UUID
    baseline_version_id: uuid.UUID
    capability_item_id: uuid.UUID
    item_state: str
    current_eligibility: bool
    document_refs: tuple[CapabilityDocumentLocation, ...]
    evidence_ids: tuple[uuid.UUID, ...]


class CapabilitySurveySourceLocationPort(Protocol):
    def resolve(
        self, transaction: object, *, capability_item_row_id: uuid.UUID,
        baseline_version_id: uuid.UUID, baseline_id: uuid.UUID,
    ) -> CapabilitySurveySourceLocation | None: ...

