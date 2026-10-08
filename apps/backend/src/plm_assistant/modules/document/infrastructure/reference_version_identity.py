"""Resolve a fixed version to its parent in the caller's transaction.

This lookup reveals no content and never proves authorization; the caller must
then use DocumentFixedSourceProofService with the same transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.document.application.reference_version_identity import (
    ReferenceVersionIdentity,
)

from .orm import DocumentRow, DocumentVersionRow
from .read_repository import _session


class SqlAlchemyReferenceVersionIdentity:
    def get(self, transaction: object, *, scope: str,
            project_id: uuid.UUID | None,
            document_version_id: uuid.UUID) -> ReferenceVersionIdentity | None:
        if (scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)
                or type(document_version_id) is not uuid.UUID
                or document_version_id.int == 0):
            return None
        row = _session(transaction).execute(
            select(DocumentVersionRow.document_id).join(
                DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
            ).where(
                DocumentVersionRow.document_version_id == document_version_id,
                DocumentVersionRow.scope == scope,
                DocumentVersionRow.project_id == project_id,
                DocumentRow.scope == scope,
                DocumentRow.project_id == project_id,
            ).with_for_update(read=True, of=(DocumentRow, DocumentVersionRow)),
        ).scalar_one_or_none()
        if row is None:
            return None
        return ReferenceVersionIdentity(row, document_version_id, scope, project_id)
