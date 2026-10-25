"""Document-owned physical content proof for Prototype Workflow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from .prototype_artifact_proof import PrototypeVersionDocumentArtifactProof


@dataclass(frozen=True, slots=True)
class PrototypeWorkflowArtifactIntegrityProof:
    document_version_id: uuid.UUID
    content_sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if (type(self.document_version_id) is not uuid.UUID
                or self.document_version_id.int == 0
                or type(self.content_sha256) is not str
                or len(self.content_sha256) != 64
                or any(value not in "0123456789abcdef"
                       for value in self.content_sha256)
                or type(self.size_bytes) is not int or self.size_bytes < 0):
            raise ValueError("invalid Prototype artifact integrity proof")


class PrototypeWorkflowArtifactIntegrityPort(Protocol):
    def prove_actual_content(
        self, transaction: object, *, project_id: uuid.UUID,
        metadata: PrototypeVersionDocumentArtifactProof,
    ) -> PrototypeWorkflowArtifactIntegrityProof | None: ...
