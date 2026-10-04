"""Minimal Evidence-owned current source facts for a caller-owned transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LockedEvidenceSource:
    evidence_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    source_parse_record_id: uuid.UUID | None
    locator: dict[str, object] = field(repr=False)
    content_fingerprint: bytes = field(repr=False)
    lock_version: int
