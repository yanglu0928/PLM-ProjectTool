"""Minimal Document-owned TEMPLATE proof consumable by Survey."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SurveyTemplateProof:
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    content_sha256: str


class SurveyTemplateProofPort(Protocol):
    def prove(self, transaction: object, *, path_project_id: uuid.UUID,
              document_id: uuid.UUID,
              document_version_id: uuid.UUID) -> SurveyTemplateProof | None: ...
