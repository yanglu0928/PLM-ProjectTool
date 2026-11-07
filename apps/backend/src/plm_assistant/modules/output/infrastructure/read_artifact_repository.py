"""Project-scoped, AVAILABLE-only OutputArtifact reference projection."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, DocumentVersionRow, FileObjectRow,
)
from plm_assistant.modules.output.application.read_artifact import (
    OutputArtifactReference,
)
from plm_assistant.modules.output.infrastructure.orm import (
    OutputArtifactRow, OutputRequestRow,
)


class SqlAlchemyOutputArtifactReadRepository:
    def get_available(self, transaction: object, *, project_id: uuid.UUID,
                      output_request_id: uuid.UUID) -> OutputArtifactReference | None:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as exc:
            raise RuntimeError("active Output transaction is required") from exc
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Output transaction is required")
        row = session.execute(
            select(
                OutputArtifactRow.output_artifact_id,
                OutputArtifactRow.output_request_id,
                OutputArtifactRow.project_id,
                OutputArtifactRow.document_id,
                OutputArtifactRow.document_version_id,
                OutputArtifactRow.artifact_kind,
                OutputArtifactRow.media_type,
                OutputArtifactRow.artifact_sha256,
                OutputArtifactRow.size_bytes,
            ).join(
                OutputRequestRow,
                OutputRequestRow.output_request_id == OutputArtifactRow.output_request_id,
            ).join(
                DocumentRow, DocumentRow.document_id == OutputArtifactRow.document_id,
            ).join(
                DocumentVersionRow,
                DocumentVersionRow.document_version_id == OutputArtifactRow.document_version_id,
            ).join(
                FileObjectRow,
                FileObjectRow.file_object_id == OutputArtifactRow.file_object_id,
            ).where(
                OutputArtifactRow.project_id == project_id,
                OutputArtifactRow.output_request_id == output_request_id,
                OutputRequestRow.project_id == project_id,
                OutputRequestRow.request_state == "SUCCEEDED",
                OutputRequestRow.output_type == OutputArtifactRow.artifact_kind,
                OutputArtifactRow.artifact_state == "AVAILABLE",
                OutputArtifactRow.scope == "PROJECT",
                DocumentRow.project_id == project_id,
                DocumentRow.scope == "PROJECT",
                DocumentRow.document_category == "GENERATED_ARTIFACT",
                DocumentRow.document_state == "ACTIVE",
                DocumentVersionRow.document_id == OutputArtifactRow.document_id,
                DocumentVersionRow.project_id == project_id,
                DocumentVersionRow.scope == "PROJECT",
                DocumentVersionRow.availability_state == "AVAILABLE",
                DocumentVersionRow.file_object_id == OutputArtifactRow.file_object_id,
                DocumentVersionRow.content_sha256 == OutputArtifactRow.artifact_sha256,
                DocumentVersionRow.size_bytes == OutputArtifactRow.size_bytes,
                DocumentVersionRow.detected_mime == OutputArtifactRow.media_type,
                FileObjectRow.project_id == project_id,
                FileObjectRow.scope == "PROJECT",
                FileObjectRow.file_state == "AVAILABLE",
                FileObjectRow.storage_class == "PERSISTENT",
                FileObjectRow.usage_kind == "DOCUMENT",
                FileObjectRow.owner_object_id.is_(None),
                FileObjectRow.sha256 == OutputArtifactRow.artifact_sha256,
                FileObjectRow.size_bytes == OutputArtifactRow.size_bytes,
                FileObjectRow.detected_mime == OutputArtifactRow.media_type,
            ),
        ).one_or_none()
        if row is None:
            return None
        if (type(row.artifact_sha256) is not bytes or len(row.artifact_sha256) != 32
                or type(row.size_bytes) is not int or row.size_bytes < 0
                or row.artifact_kind not in {"DOCX", "PPTX", "PNG", "JPEG"}):
            raise RuntimeError("invalid OutputArtifact read projection")
        return OutputArtifactReference(
            row.output_artifact_id, row.output_request_id, row.project_id,
            row.document_id, row.document_version_id, row.artifact_kind,
            row.media_type, row.artifact_sha256.hex(), row.size_bytes,
        )
