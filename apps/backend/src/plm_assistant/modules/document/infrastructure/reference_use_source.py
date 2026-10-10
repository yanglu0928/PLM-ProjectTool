"""Document-owned locked fixed-version metadata for internal Reference use."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.document.application.prove_reference_use_document import (
    CurrentReferenceDocumentSource,
)

from .orm import DocumentRow, DocumentVersionRow, FileObjectRow
from .read_repository import _session


class SqlAlchemyReferenceUseDocumentSource:
    def current(self, transaction: object, *, scope: str,
                project_id: uuid.UUID | None,
                document_version_id: uuid.UUID) -> CurrentReferenceDocumentSource | None:
        if (scope not in ("PROJECT", "GLOBAL")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(document_version_id) is not uuid.UUID
                or document_version_id.int == 0):
            return None
        row = _session(transaction).execute(select(
            DocumentRow, DocumentVersionRow, FileObjectRow,
        ).join(
            DocumentVersionRow,
            DocumentVersionRow.document_id == DocumentRow.document_id,
        ).join(
            FileObjectRow,
            FileObjectRow.file_object_id == DocumentVersionRow.file_object_id,
        ).where(
            DocumentVersionRow.document_version_id == document_version_id,
            DocumentRow.scope == scope,
            DocumentRow.project_id == project_id,
            DocumentRow.document_state.in_(("ACTIVE", "ARCHIVED")),
            DocumentVersionRow.scope == scope,
            DocumentVersionRow.project_id == project_id,
            DocumentVersionRow.availability_state == "AVAILABLE",
            FileObjectRow.scope == scope,
            FileObjectRow.project_id == project_id,
            FileObjectRow.storage_class == "PERSISTENT",
            FileObjectRow.file_state == "AVAILABLE",
            FileObjectRow.sha256 == DocumentVersionRow.content_sha256,
            FileObjectRow.size_bytes == DocumentVersionRow.size_bytes,
            FileObjectRow.detected_mime == DocumentVersionRow.detected_mime,
        ).with_for_update(
            read=True, of=(DocumentRow, DocumentVersionRow, FileObjectRow),
        )).one_or_none()
        if row is None:
            return None
        document, version, file = row
        return CurrentReferenceDocumentSource(
            document.document_id, version.document_version_id,
            document.scope, document.project_id, document.document_category,
            bytes(version.content_sha256), version.size_bytes,
            version.detected_mime, file.storage_locator,
        )
