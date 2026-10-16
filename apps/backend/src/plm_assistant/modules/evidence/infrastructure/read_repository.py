"""Evidence-owned bounded metadata reads; no Document table or private path access."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from plm_assistant.modules.evidence.application.read_evidence import EvidencePage, EvidenceView
from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Evidence transaction is required")
    return session


def _view(row: EvidenceRow) -> EvidenceView:
    return EvidenceView(
        row.evidence_id, row.scope, row.project_id,
        row.document_id, row.document_version_id,
        row.locator_payload, row.content_fingerprint,
        row.display_label, row.display_excerpt,
        row.eligibility_state, row.created_at,
        f'"v{row.lock_version}"',
        row.source_parse_record_id,
    )


class SqlAlchemyEvidenceReadRepository:
    @staticmethod
    def _visible(scope: str, project_id: uuid.UUID | None):
        return select(EvidenceRow).where(
            EvidenceRow.scope == scope,
            EvidenceRow.project_id == project_id,
        )

    def list(self, transaction: object, *, scope: str,
             project_id: uuid.UUID | None,
             after: tuple[datetime, uuid.UUID] | None,
             limit: int) -> EvidencePage:
        statement = self._visible(scope, project_id)
        if after is not None:
            statement = statement.where(or_(
                EvidenceRow.created_at > after[0],
                and_(EvidenceRow.created_at == after[0],
                     EvidenceRow.evidence_id > after[1]),
            ))
        rows = _session(transaction).execute(
            statement.order_by(EvidenceRow.created_at,
                               EvidenceRow.evidence_id).limit(limit + 1),
        ).scalars().all()
        more = len(rows) > limit
        items = tuple(_view(row) for row in rows[:limit])
        next_after = ((items[-1].created_at, items[-1].evidence_id)
                      if more and items else None)
        return EvidencePage(items, next_after, more)

    def get(self, transaction: object, *, scope: str,
            project_id: uuid.UUID | None,
            evidence_id: uuid.UUID) -> EvidenceView | None:
        row = _session(transaction).execute(
            self._visible(scope, project_id).where(
                EvidenceRow.evidence_id == evidence_id,
            ),
        ).scalar_one_or_none()
        return None if row is None else _view(row)
