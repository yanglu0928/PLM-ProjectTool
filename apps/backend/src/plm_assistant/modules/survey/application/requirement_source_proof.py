"""Minimal Survey-owned approved Conclusion proof for Requirement writes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SurveyConclusionRequirementSourceProof:
    survey_conclusion_id: uuid.UUID
    conclusion_series_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    version_no: int
    content_fingerprint: bytes = field(repr=False)


class SurveyConclusionRequirementSourceProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_conclusion_id: uuid.UUID,
    ) -> SurveyConclusionRequirementSourceProof | None: ...
