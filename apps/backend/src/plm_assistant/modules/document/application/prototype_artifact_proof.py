"""Document-owned fixed artifact proof for PrototypeTemplate versions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PrototypeDocumentArtifactProof:
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    content_sha256: str


class PrototypeDocumentArtifactProofPort(Protocol):
    def prove(
        self, transaction: object, *, template_scope: str,
        project_id: uuid.UUID | None, document_version_id: uuid.UUID,
    ) -> PrototypeDocumentArtifactProof | None: ...
