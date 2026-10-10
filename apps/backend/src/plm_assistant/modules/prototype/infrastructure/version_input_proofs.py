"""SQL proof of a fixed PUBLISHED TemplateVersion usable by one project."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.version_input_proofs import (
    PrototypeVersionTemplateProof,
)

from .orm import PrototypeTemplateRow, PrototypeTemplateVersionRow


class SqlAlchemyPrototypeVersionTemplateProof:
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_template_id: uuid.UUID,
        prototype_template_version_id: uuid.UUID,
    ) -> PrototypeVersionTemplateProof | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
            project_id, prototype_template_id, prototype_template_version_id,
        )):
            return None
        session = self._session(transaction)
        allowed_scope = (
            (PrototypeTemplateRow.scope == "GLOBAL")
            & PrototypeTemplateRow.project_id.is_(None)
            & (PrototypeTemplateVersionRow.scope == "GLOBAL")
            & PrototypeTemplateVersionRow.project_id.is_(None)
        ) | (
            (PrototypeTemplateRow.scope == "PROJECT")
            & (PrototypeTemplateRow.project_id == project_id)
            & (PrototypeTemplateVersionRow.scope == "PROJECT")
            & (PrototypeTemplateVersionRow.project_id == project_id)
        )
        row = session.execute(select(
            PrototypeTemplateVersionRow.prototype_template_id,
            PrototypeTemplateVersionRow.prototype_template_version_id,
            PrototypeTemplateVersionRow.scope,
            PrototypeTemplateVersionRow.project_id,
            PrototypeTemplateVersionRow.version_no,
            PrototypeTemplateVersionRow.content_fingerprint,
        ).join(
            PrototypeTemplateRow,
            PrototypeTemplateRow.prototype_template_id
            == PrototypeTemplateVersionRow.prototype_template_id,
        ).where(
            PrototypeTemplateRow.prototype_template_id == prototype_template_id,
            PrototypeTemplateRow.template_state == "ACTIVE",
            PrototypeTemplateVersionRow.prototype_template_version_id
            == prototype_template_version_id,
            PrototypeTemplateVersionRow.version_state == "PUBLISHED",
            allowed_scope,
        ).with_for_update(
            read=True, of=(PrototypeTemplateRow, PrototypeTemplateVersionRow),
        )).one_or_none()
        if row is None:
            return None
        return PrototypeVersionTemplateProof(
            row.prototype_template_id, row.prototype_template_version_id,
            row.scope, row.project_id, row.version_no,
            bytes(row.content_fingerprint).hex(),
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Prototype transaction is required") from error
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Prototype transaction is required")
        return session
