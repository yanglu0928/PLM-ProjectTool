"""Document-owned fixed TEMPLATE proof for authorized Survey writes."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.survey_template_proof import (
    SurveyTemplateProof,
)

from .orm import DocumentRow, DocumentVersionRow


class SqlAlchemySurveyTemplateProof:
    def prove(self, transaction: object, *, path_project_id: uuid.UUID,
              document_id: uuid.UUID,
              document_version_id: uuid.UUID) -> SurveyTemplateProof | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
                path_project_id, document_id, document_version_id)):
            return None
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Document transaction is required")
        row = session.execute(select(
            DocumentVersionRow.document_version_id, DocumentVersionRow.document_id,
            DocumentVersionRow.scope, DocumentVersionRow.project_id,
            DocumentVersionRow.content_sha256,
        ).join(DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id).where(
            DocumentVersionRow.document_version_id == document_version_id,
            DocumentVersionRow.document_id == document_id,
            DocumentVersionRow.availability_state == "AVAILABLE",
            DocumentRow.document_state == "ACTIVE",
            DocumentRow.document_category == "TEMPLATE",
            ((DocumentVersionRow.scope == "GLOBAL")
             & DocumentVersionRow.project_id.is_(None)
             & (DocumentRow.scope == "GLOBAL") & DocumentRow.project_id.is_(None)
             | (DocumentVersionRow.scope == "PROJECT")
             & (DocumentVersionRow.project_id == path_project_id)
             & (DocumentRow.scope == "PROJECT")
             & (DocumentRow.project_id == path_project_id)),
        ).with_for_update(read=True)).one_or_none()
        return None if row is None else SurveyTemplateProof(
            row.document_version_id, row.document_id, row.scope, row.project_id,
            bytes(row.content_sha256).hex(),
        )
