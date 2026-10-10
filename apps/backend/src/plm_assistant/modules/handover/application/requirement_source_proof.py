"""Minimal Handover-owned current approved proof for Requirement writes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HandoverRequirementSourceProof:
    handover_analysis_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    project_id: uuid.UUID
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    version_no: int
    content_fingerprint: bytes = field(repr=False)


class HandoverRequirementSourceProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
    ) -> HandoverRequirementSourceProof | None: ...
