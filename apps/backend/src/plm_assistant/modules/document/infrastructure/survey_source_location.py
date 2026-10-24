"""Document-owned historical/public Survey TEMPLATE source resolver."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.survey_source_location import (
    DocumentSurveySourceLocation,
)

from .orm import DocumentRow, DocumentVersionRow


class SqlAlchemyDocumentSurveySourceLocation:
    def resolve(
        self, transaction: object, *, path_project_id: uuid.UUID,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
    ) -> DocumentSurveySourceLocation | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
                path_project_id, document_id, document_version_id)):
            return None
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Document transaction is required")
        row = session.execute(select(
            DocumentVersionRow.scope, DocumentVersionRow.project_id,
            DocumentVersionRow.availability_state,
            DocumentRow.scope.label("document_scope"),
            DocumentRow.project_id.label("document_project_id"),
            DocumentRow.document_category, DocumentRow.document_state,
        ).join(
            DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
        ).where(
            DocumentVersionRow.document_version_id == document_version_id,
            DocumentVersionRow.document_id == document_id,
            DocumentRow.document_id == document_id,
            ((DocumentVersionRow.scope == "GLOBAL")
             & DocumentVersionRow.project_id.is_(None)
             & (DocumentRow.scope == "GLOBAL")
             & DocumentRow.project_id.is_(None)
             | (DocumentVersionRow.scope == "PROJECT")
             & (DocumentVersionRow.project_id == path_project_id)
             & (DocumentRow.scope == "PROJECT")
             & (DocumentRow.project_id == path_project_id)),
        ).with_for_update(read=True)).one_or_none()
        if row is None:
            return None
        current = (
            row.availability_state == "AVAILABLE"
            and row.document_category == "TEMPLATE"
            and row.document_state == "ACTIVE"
        )
        return DocumentSurveySourceLocation(
            document_id, document_version_id, row.scope, row.project_id, current,
        )

