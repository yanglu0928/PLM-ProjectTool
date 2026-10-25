"""Document-owned public location target for an immutable Survey TEMPLATE source."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DocumentSurveySourceLocation:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    current_eligibility: bool


class DocumentSurveySourceLocationPort(Protocol):
    def resolve(
        self, transaction: object, *, path_project_id: uuid.UUID,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
    ) -> DocumentSurveySourceLocation | None: ...

