"""Minimal Evidence-owned current PROJECT proof for Requirement writes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EvidenceRequirementSourceProof:
    evidence_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_lock_version: int
    content_fingerprint: bytes = field(repr=False)


class EvidenceRequirementSourceProofPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        evidence_id: uuid.UUID,
    ) -> EvidenceRequirementSourceProof | None: ...
