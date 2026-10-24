"""AI-owned completed SURVEY_ANALYZE provenance proof."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SurveyConclusionAITaskProof:
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    invocation_id: uuid.UUID
    suggestion_payload_id: uuid.UUID
    payload_fingerprint: bytes = field(repr=False)
    suggestion_state: str = "AVAILABLE"
    fact_status: str = "NOT_FORMAL_FACT"
    completed_at: datetime | None = None


class SurveyConclusionAITaskOwner(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              ai_task_id: uuid.UUID) -> SurveyConclusionAITaskProof | None: ...
