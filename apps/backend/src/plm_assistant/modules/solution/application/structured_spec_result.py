"""Immutable first-result projection for an internal SOL-06 DRAFT write."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .structured_spec_input import SpecRequirementRef, SpecSectionRef


@dataclass(frozen=True, slots=True)
class StructuredSpecInitialView:
    structured_solution_spec_id: uuid.UUID
    spec_series_id: uuid.UUID
    project_id: uuid.UUID
    spec_type: str
    version_no: int
    content_fingerprint: bytes = field(repr=False)
    payload_json: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    requirement_refs: tuple[SpecRequirementRef, ...]
    section_refs: tuple[SpecSectionRef, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    supersedes_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    version_state: str = "DRAFT"
    artifact_ids: tuple[uuid.UUID, ...] = ()
    review_ref: None = None
    review_round_ref: None = None

    def payload(self) -> dict[str, object]:
        return json.loads(self.payload_json)
