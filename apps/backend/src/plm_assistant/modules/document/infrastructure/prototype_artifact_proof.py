"""SQL proof for fixed DocumentVersion artifacts used by PrototypeTemplate."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeDocumentArtifactProof, PrototypeVersionDocumentArtifactProof,
)

from .orm import DocumentRow, DocumentVersionRow, FileObjectRow


class SqlAlchemyPrototypeDocumentArtifactProof:
    def prove(
        self, transaction: object, *, template_scope: str,
        project_id: uuid.UUID | None, document_version_id: uuid.UUID,
    ) -> PrototypeDocumentArtifactProof | None:
        if (
            template_scope not in {"GLOBAL", "PROJECT"}
            or (template_scope == "GLOBAL" and project_id is not None)
            or (template_scope == "PROJECT" and (
                type(project_id) is not uuid.UUID or project_id.int == 0
            ))
            or type(document_version_id) is not uuid.UUID
            or document_version_id.int == 0
        ):
            return None
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Document transaction is required") from error
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Document transaction is required")
        allowed_scope = (
            (DocumentVersionRow.scope == "GLOBAL")
            & DocumentVersionRow.project_id.is_(None)
            & (DocumentRow.scope == "GLOBAL")
            & DocumentRow.project_id.is_(None)
            & (FileObjectRow.scope == "GLOBAL")
            & FileObjectRow.project_id.is_(None)
        )
        if template_scope == "PROJECT":
            allowed_scope = allowed_scope | (
                (DocumentVersionRow.scope == "PROJECT")
                & (DocumentVersionRow.project_id == project_id)
                & (DocumentRow.scope == "PROJECT")
                & (DocumentRow.project_id == project_id)
                & (FileObjectRow.scope == "PROJECT")
                & (FileObjectRow.project_id == project_id)
            )
        row = session.execute(select(
            DocumentVersionRow.document_version_id,
            DocumentVersionRow.document_id,
            DocumentVersionRow.scope,
            DocumentVersionRow.project_id,
            DocumentVersionRow.content_sha256,
        ).join(
            DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
        ).join(
            FileObjectRow,
            FileObjectRow.file_object_id == DocumentVersionRow.file_object_id,
        ).where(
            DocumentVersionRow.document_version_id == document_version_id,
            DocumentVersionRow.availability_state == "AVAILABLE",
            DocumentRow.document_state == "ACTIVE",
            FileObjectRow.file_state == "AVAILABLE",
            allowed_scope,
        ).with_for_update(
            read=True, of=(DocumentVersionRow, DocumentRow, FileObjectRow),
        )).one_or_none()
        return None if row is None else PrototypeDocumentArtifactProof(
            row.document_version_id, row.document_id, row.scope, row.project_id,
            bytes(row.content_sha256).hex(),
        )

    def prove_for_prototype_version(
        self, transaction: object, *, project_id: uuid.UUID,
        document_version_id: uuid.UUID,
    ) -> PrototypeVersionDocumentArtifactProof | None:
        if (
            type(project_id) is not uuid.UUID or project_id.int == 0
            or type(document_version_id) is not uuid.UUID
            or document_version_id.int == 0
        ):
            return None
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Document transaction is required") from error
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Document transaction is required")
        allowed_scope = (
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
            DocumentVersionRow.document_version_id,
            DocumentVersionRow.document_id,
            DocumentVersionRow.scope,
            DocumentVersionRow.project_id,
            DocumentVersionRow.content_sha256,
            DocumentVersionRow.size_bytes,
            DocumentVersionRow.detected_mime,
        ).join(
            DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
        ).join(
            FileObjectRow,
            FileObjectRow.file_object_id == DocumentVersionRow.file_object_id,
        ).where(
            DocumentVersionRow.document_version_id == document_version_id,
            DocumentVersionRow.availability_state == "AVAILABLE",
            DocumentRow.document_state == "ACTIVE",
            FileObjectRow.file_state == "AVAILABLE",
            allowed_scope,
        ).with_for_update(
            read=True, of=(DocumentVersionRow, DocumentRow, FileObjectRow),
        )).one_or_none()
        return None if row is None else PrototypeVersionDocumentArtifactProof(
            row.document_version_id, row.document_id, row.scope, row.project_id,
            bytes(row.content_sha256).hex(), row.size_bytes, row.detected_mime,
        )
