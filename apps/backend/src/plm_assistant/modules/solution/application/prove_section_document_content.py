"""Opaque fixed PROJECT DocumentVersion content proof for SectionVersion."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


class SectionDocumentContentError(RuntimeError):
    def __init__(self, code: str = "SOURCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SectionDocumentContentProof:
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    content_sha256: bytes = field(repr=False)


class SectionDocumentContentPort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              document_version_id: uuid.UUID) -> SectionDocumentContentProof: ...
