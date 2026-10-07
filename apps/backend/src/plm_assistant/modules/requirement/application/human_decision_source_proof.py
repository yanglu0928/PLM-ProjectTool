"""Minimal Requirement-owned formal human decision proof for Version writes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RequirementHumanDecisionSourceProof:
    decision_id: uuid.UUID
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    decision_type: str
    decided_by: uuid.UUID
    decided_at: datetime
    before_version: int
    after_version: int
    evidence_refs: tuple[uuid.UUID, ...]


class RequirementHumanDecisionSourceProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        decision_id: uuid.UUID,
    ) -> RequirementHumanDecisionSourceProof | None: ...
