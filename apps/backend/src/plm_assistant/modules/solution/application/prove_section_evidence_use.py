"""Minimal current PROJECT Evidence proof for a SectionVersion write."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


class SectionEvidenceUseError(RuntimeError):
    def __init__(self, code: str = "EVIDENCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SectionEvidenceUseProof:
    evidence_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_lock_version: int
    content_fingerprint: bytes = field(repr=False)


class SectionEvidenceUsePort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              evidence_id: uuid.UUID) -> SectionEvidenceUseProof: ...
