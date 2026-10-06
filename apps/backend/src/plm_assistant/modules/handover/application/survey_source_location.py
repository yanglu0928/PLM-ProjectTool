"""Handover-owned public location target for an immutable Survey source."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HandoverSurveySourceLocation:
    handover_analysis_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    analysis_item_id: uuid.UUID
    item_state: str
    current_eligibility: bool
    evidence_ids: tuple[uuid.UUID, ...]


class HandoverSurveySourceLocationPort(Protocol):
    def resolve(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_item_row_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
    ) -> HandoverSurveySourceLocation | None: ...

