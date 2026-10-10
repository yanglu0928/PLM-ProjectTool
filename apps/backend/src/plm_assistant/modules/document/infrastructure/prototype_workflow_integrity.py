"""Physically verify fixed DocumentVersion bytes without leaking file paths."""

from __future__ import annotations

import hmac
import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.document.application.prototype_workflow_integrity import (
    PrototypeWorkflowArtifactIntegrityProof,
)

from .orm import DocumentRow, DocumentVersionRow, FileObjectRow


class VerifiedContentStoragePort(Protocol):
    def verify_content(self, locator: str, *, expected_sha256: bytes,
                       expected_size: int, max_bytes: int) -> object: ...


class SqlAlchemyPrototypeWorkflowArtifactIntegrityProof:
    def __init__(self, *, storage: VerifiedContentStoragePort,
                 max_bytes: int = 100_000_000) -> None:
        if (storage is None or type(max_bytes) is not int
                or not 0 < max_bytes <= 100_000_000):
            raise ValueError("bounded Document storage proof required")
        self._storage, self._max_bytes = storage, max_bytes

    def prove_actual_content(
        self, transaction: object, *, project_id: uuid.UUID,
        metadata: PrototypeVersionDocumentArtifactProof,
    ) -> PrototypeWorkflowArtifactIntegrityProof | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(metadata) is not PrototypeVersionDocumentArtifactProof
                or metadata.scope == "PROJECT" and metadata.project_id != project_id
                or metadata.size_bytes > self._max_bytes):
            return None
        metadata.__post_init__()
        session = getattr(transaction, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Document transaction required")
        allowed = (
            (DocumentVersionRow.scope == "GLOBAL")
            & DocumentVersionRow.project_id.is_(None)
            & (DocumentRow.scope == "GLOBAL")
            & DocumentRow.project_id.is_(None)
            & (FileObjectRow.scope == "GLOBAL")
            & FileObjectRow.project_id.is_(None)
        ) | (
            (DocumentVersionRow.scope == "PROJECT")
            & (DocumentVersionRow.project_id == project_id)
            & (DocumentRow.scope == "PROJECT")
            & (DocumentRow.project_id == project_id)
            & (FileObjectRow.scope == "PROJECT")
            & (FileObjectRow.project_id == project_id)
        )
        row = session.execute(select(
            DocumentVersionRow, FileObjectRow,
        ).join(
            DocumentRow,
            DocumentRow.document_id == DocumentVersionRow.document_id,
        ).join(
            FileObjectRow,
            FileObjectRow.file_object_id == DocumentVersionRow.file_object_id,
        ).where(
            DocumentVersionRow.document_version_id == metadata.document_version_id,
            DocumentVersionRow.document_id == metadata.document_id,
            DocumentVersionRow.availability_state == "AVAILABLE",
            DocumentRow.document_state == "ACTIVE",
            FileObjectRow.file_state == "AVAILABLE",
            FileObjectRow.storage_class == "PERSISTENT",
            allowed,
        ).with_for_update(
            read=True, of=(DocumentVersionRow, DocumentRow, FileObjectRow),
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None:
            return None
        version, file = row
        expected = bytes.fromhex(metadata.content_sha256)
        if (version.scope != metadata.scope
                or version.project_id != metadata.project_id
                or file.scope != metadata.scope
                or file.project_id != metadata.project_id
                or version.size_bytes != metadata.size_bytes
                or file.size_bytes != metadata.size_bytes
                or version.detected_mime != metadata.detected_mime
                or file.detected_mime != metadata.detected_mime
                or type(file.sha256) is not bytes
                or not hmac.compare_digest(bytes(version.content_sha256), expected)
                or not hmac.compare_digest(bytes(file.sha256), expected)):
            return None
        try:
            physical = self._storage.verify_content(
                file.storage_locator, expected_sha256=expected,
                expected_size=metadata.size_bytes, max_bytes=self._max_bytes,
            )
        except Exception:
            return None
        if (getattr(physical, "sha256", None) != expected
                or getattr(physical, "size_bytes", None) != metadata.size_bytes):
            return None
        return PrototypeWorkflowArtifactIntegrityProof(
            metadata.document_version_id, metadata.content_sha256,
            metadata.size_bytes,
        )
