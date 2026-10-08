"""Requirement-owned stable acceptance IDs for Prototype Workflow coverage."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RequirementAcceptanceRefsProof:
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    criterion_refs: tuple[uuid.UUID, ...]

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0
                for value in (self.project_id, self.requirement_id,
                              self.requirement_version_id))
                or type(self.criterion_refs) is not tuple
                or not self.criterion_refs
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in self.criterion_refs)
                or len(set(self.criterion_refs)) != len(self.criterion_refs)):
            raise ValueError("invalid Requirement acceptance refs")


class RequirementAcceptanceRefsProofPort(Protocol):
    def prove_current_acceptance_refs(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> RequirementAcceptanceRefsProof | None: ...
