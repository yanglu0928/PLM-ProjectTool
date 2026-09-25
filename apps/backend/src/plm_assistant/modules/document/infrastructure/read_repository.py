"""Document-owned bounded metadata keyset reads; no storage locator projection."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.read_documents import (
    DocumentPage, DocumentVersionPage, DocumentVersionView, DocumentView,
)
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, DocumentVersionRow, FileObjectRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Document transaction is required")
    return session


def _view(row: DocumentRow) -> DocumentView:
    return DocumentView(
        row.document_id, row.scope, row.project_id,
        row.document_category, row.document_subtype,
        row.title, row.original_display_name, row.document_state,
        row.latest_version_ref, row.effective_version_ref,
        row.created_at, f'"v{row.lock_version}"',
    )


class SqlAlchemyDocumentReadRepository:
    @staticmethod
    def _visible(scope: str, project_id: uuid.UUID | None):
        return select(DocumentRow).where(
            DocumentRow.scope == scope,
            DocumentRow.project_id == project_id,
            DocumentRow.document_state.in_(("ACTIVE", "ARCHIVED")),
        )

    def list(self, transaction: object, *, scope: str,
             project_id: uuid.UUID | None, after_document_id: uuid.UUID | None,
             limit: int) -> DocumentPage:
        statement = self._visible(scope, project_id)
        if after_document_id is not None:
            statement = statement.where(DocumentRow.document_id > after_document_id)
        rows = _session(transaction).execute(
            statement.order_by(DocumentRow.document_id).limit(limit + 1),
        ).scalars().all()
        more = len(rows) > limit
        items = tuple(_view(row) for row in rows[:limit])
        return DocumentPage(items, items[-1].document_id if more else None, more)

    def get(self, transaction: object, *, scope: str,
            project_id: uuid.UUID | None, document_id: uuid.UUID) -> DocumentView | None:
        row = _session(transaction).execute(
            self._visible(scope, project_id).where(
                DocumentRow.document_id == document_id,
            ),
        ).scalar_one_or_none()
        return None if row is None else _view(row)

    @staticmethod
    def _visible_versions(scope: str, project_id: uuid.UUID | None,
                          document_id: uuid.UUID):
        return select(DocumentVersionRow).join(
            FileObjectRow,
            FileObjectRow.file_object_id == DocumentVersionRow.file_object_id,
        ).where(
            DocumentVersionRow.document_id == document_id,
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
        )

    def list_versions(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None, document_id: uuid.UUID,
                      before_version_no: int | None, limit: int) -> DocumentVersionPage:
        statement = self._visible_versions(scope, project_id, document_id)
        if before_version_no is not None:
            statement = statement.where(DocumentVersionRow.version_no < before_version_no)
        rows = _session(transaction).execute(
            statement.order_by(DocumentVersionRow.version_no.desc()).limit(limit + 1),
        ).scalars().all()
        more = len(rows) > limit
        items = tuple(_version_view(row) for row in rows[:limit])
        return DocumentVersionPage(items, items[-1].version_no if more else None, more)

    def get_version(self, transaction: object, *, scope: str,
                    project_id: uuid.UUID | None, document_id: uuid.UUID,
                    document_version_id: uuid.UUID) -> DocumentVersionView | None:
        row = _session(transaction).execute(
            self._visible_versions(scope, project_id, document_id).where(
                DocumentVersionRow.document_version_id == document_version_id,
            ),
        ).scalar_one_or_none()
        return None if row is None else _version_view(row)


def _version_view(row: DocumentVersionRow) -> DocumentVersionView:
    return DocumentVersionView(
        row.document_version_id, row.document_id, row.version_no,
        row.content_sha256.hex(), row.size_bytes, row.detected_mime,
        row.availability_state, row.supersedes_version_ref,
        row.created_at, row.integrity_checked_at,
    )
