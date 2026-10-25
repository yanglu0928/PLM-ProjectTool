"""Minimal Handover-owned proof consumable by Survey."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HandoverSurveySourceProof:
    analysis_item_row_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    project_id: uuid.UUID
    item_state: str


class HandoverSurveySourceProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_item_row_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
    ) -> HandoverSurveySourceProof | None: ...
