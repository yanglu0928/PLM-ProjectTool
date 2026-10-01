"""Minimal locked Evidence facts for a first eligibility decision."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LockedEvidenceEligibility:
    evidence_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    content_fingerprint: bytes = field(repr=False)
    eligibility_state: str
    lock_version: int
