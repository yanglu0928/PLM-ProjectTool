"""Historical fixed OutlineVersion read DTOs; no current source eligibility claim."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .outline_version_input import OutlineReferenceRef, OutlineRequirementRef


@dataclass(frozen=True, slots=True)
class OutlineVersionHistoryView:
    solution_outline_version_id: uuid.UUID
    solution_outline_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    section_ids: tuple[uuid.UUID, ...]
    requirement_refs: tuple[OutlineRequirementRef, ...]
    reference_refs: tuple[OutlineReferenceRef, ...]
    missing_declarations: tuple[dict[str, object], ...] = field(repr=False)
    conflict_declarations: tuple[dict[str, object], ...] = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
