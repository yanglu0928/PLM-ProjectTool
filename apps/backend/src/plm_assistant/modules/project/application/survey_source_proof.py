"""Minimal Project Department proof consumable by Survey."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SurveyTargetDepartmentProof:
    department_id: uuid.UUID
    project_id: uuid.UUID
    state: str


class SurveyTargetDepartmentProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> SurveyTargetDepartmentProof | None: ...
