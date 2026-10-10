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


@dataclass(frozen=True, slots=True)
class PrototypeVersionDocumentArtifactProof:
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    content_sha256: str
    size_bytes: int
    detected_mime: str

    def __post_init__(self) -> None:
        project_shape = (
            self.scope == "GLOBAL" and self.project_id is None
            or self.scope == "PROJECT" and type(self.project_id) is uuid.UUID
            and self.project_id.int != 0
        )
        if (
            any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.document_version_id, self.document_id,
            ))
            or not project_shape
            or len(self.content_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.content_sha256)
            or type(self.size_bytes) is not int or self.size_bytes < 0
            or type(self.detected_mime) is not str
            or not 1 <= len(self.detected_mime) <= 255
        ):
            raise ValueError("invalid PrototypeVersion Document artifact proof")


class PrototypeVersionDocumentArtifactProofPort(Protocol):
    def prove_for_prototype_version(
        self, transaction: object, *, project_id: uuid.UUID,
        document_version_id: uuid.UUID,
    ) -> PrototypeVersionDocumentArtifactProof | None: ...
