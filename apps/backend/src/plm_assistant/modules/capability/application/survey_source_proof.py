"""Minimal Capability-owned proof consumable by Survey."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CapabilitySurveySourceProof:
    capability_item_row_id: uuid.UUID
    baseline_version_id: uuid.UUID
    baseline_id: uuid.UUID
    capability_item_id: uuid.UUID
    item_state: str


class CapabilitySurveySourceProofPort(Protocol):
    def prove(
        self, transaction: object, *, capability_item_row_id: uuid.UUID,
        baseline_version_id: uuid.UUID, baseline_id: uuid.UUID,
    ) -> CapabilitySurveySourceProof | None: ...
