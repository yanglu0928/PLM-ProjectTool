"""Handover-owned current Action proof for SurveyConclusion open issues."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SurveyConclusionIssueProof:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    action_type: str
    action_state: str
    lock_version: int
    updated_at: datetime


class SurveyConclusionIssueOwner(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              action_item_id: uuid.UUID) -> SurveyConclusionIssueProof | None: ...
