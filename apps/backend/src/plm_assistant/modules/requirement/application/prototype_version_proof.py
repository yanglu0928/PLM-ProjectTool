"""Requirement-owned proof consumed by PrototypeVersion creation and validation."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PrototypeApprovedRequirementVersionProof:
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    version_no: int
    content_fingerprint: str
    review_id: uuid.UUID
    review_round_id: uuid.UUID

    def __post_init__(self) -> None:
        if (
            any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.project_id, self.requirement_id, self.requirement_version_id,
                self.review_id, self.review_round_id,
            ))
            or type(self.version_no) is not int or self.version_no < 1
            or re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint) is None
        ):
            raise ValueError("invalid approved RequirementVersion proof")


class PrototypeApprovedRequirementVersionProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> PrototypeApprovedRequirementVersionProof | None: ...
