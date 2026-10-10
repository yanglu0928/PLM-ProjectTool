"""Candidate Evidence persistence; caller owns authorization, proof and transaction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.evidence.application.create_evidence import CreateEvidence
from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow


class SqlAlchemyEvidenceCreateRepository:
    @staticmethod
    def _session(transaction: object) -> Session:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Evidence transaction is required")
        return session

    def create(self, transaction: object, *, command: CreateEvidence,
               locator: dict[str, object], fingerprint: bytes) -> tuple[uuid.UUID, datetime]:
        session = self._session(transaction)
        row = session.execute(insert(EvidenceRow).values(
            scope=command.scope, project_id=command.project_id,
            document_id=command.document_id,
            document_version_id=command.document_version_id,
            source_parse_record_id=command.parse_record_id,
            locator_type=locator["locator_type"], locator_payload=locator,
            content_fingerprint=fingerprint, display_label=command.display_label,
            display_excerpt=command.display_excerpt, eligibility_state="CANDIDATE",
            created_by=command.actor_id,
        ).returning(EvidenceRow.evidence_id, EvidenceRow.created_at)).one()
        return row.evidence_id, row.created_at

    def replay(self, transaction: object, evidence_id: uuid.UUID, *,
               command: CreateEvidence, locator: dict[str, object],
               fingerprint: bytes) -> datetime | None:
        session = self._session(transaction)
        row = session.execute(select(
            EvidenceRow.created_at, EvidenceRow.content_fingerprint,
            EvidenceRow.locator_payload, EvidenceRow.display_label,
            EvidenceRow.display_excerpt,
            EvidenceRow.source_parse_record_id,
        ).where(
            EvidenceRow.evidence_id == evidence_id,
            EvidenceRow.scope == command.scope,
            EvidenceRow.project_id == command.project_id,
            EvidenceRow.document_id == command.document_id,
            EvidenceRow.document_version_id == command.document_version_id,
            EvidenceRow.created_by == command.actor_id,
        )).one_or_none()
        if row is None or (row.content_fingerprint != fingerprint
                           or row.locator_payload != locator
                           or row.source_parse_record_id != command.parse_record_id
                           or row.display_label != command.display_label
                           or row.display_excerpt != command.display_excerpt):
            return None
        return row.created_at
