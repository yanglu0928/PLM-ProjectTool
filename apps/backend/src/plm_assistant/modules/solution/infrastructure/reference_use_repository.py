"""Solution-owned locked Reference eligibility and confirmation use facts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from plm_assistant.modules.solution.application.prove_reference_use import (
    CurrentGlobalConfirmationProof,
    CurrentReferenceUseSnapshot,
    ReferenceUseQuery,
)

from .orm import (
    ReferenceDeidentificationConfirmationRow as Confirmation,
    ReferenceSolutionDocumentRefRow as DocumentRef,
    ReferenceSolutionEligibilityEventRow as Event,
    ReferenceSolutionEvidenceRefRow as EvidenceRef,
    ReferenceSolutionRow as Root,
    ReferenceSolutionVersionRow as Version,
)
from .reference_deidentification_repository import _session


class SqlAlchemyCurrentReferenceUseRepository:
    """Current root/event set, locked until the caller's transaction commits."""

    def current(self, transaction: object, *, query: ReferenceUseQuery,
                now: datetime) -> CurrentReferenceUseSnapshot | None:
        if (type(query) is not ReferenceUseQuery
                or type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None
                or type(query.reference_solution_id) is not uuid.UUID
                or query.reference_solution_id.int == 0
                or type(query.reference_version_id) is not uuid.UUID
                or query.reference_version_id.int == 0
                or type(query.target_project_id) is not uuid.UUID
                or query.target_project_id.int == 0
                or query.scope not in ("PROJECT", "GLOBAL")):
            return None
        session = _session(transaction)
        source_project_id = query.target_project_id if query.scope == "PROJECT" else None
        root = session.execute(select(Root).where(
            Root.reference_solution_id == query.reference_solution_id,
            Root.scope == query.scope,
            Root.project_id == source_project_id,
        ).with_for_update(of=Root)).scalar_one_or_none()
        if (root is None or root.current_version_ref != query.reference_version_id
                or root.eligibility_state != "ELIGIBLE"):
            return None
        version = session.execute(select(Version).where(
            Version.reference_version_id == query.reference_version_id,
            Version.reference_solution_id == query.reference_solution_id,
            Version.scope == query.scope,
            Version.project_id == source_project_id,
        ).with_for_update(read=True, of=Version)).scalar_one_or_none()
        if version is None or version.version_state != "DRAFT":
            return None
        event = session.execute(select(Event).where(
            Event.reference_solution_id == query.reference_solution_id,
        ).order_by(Event.result_lock_version.desc()).limit(1).with_for_update(
            read=True, of=Event)).scalar_one_or_none()
        if (event is None or event.event_kind != "HUMAN"
                or event.scope != query.scope
                or event.project_id != source_project_id
                or event.reference_version_id != query.reference_version_id
                or event.result_state != "ELIGIBLE"
                or event.result_lock_version != root.lock_version):
            return None
        documents = tuple(session.execute(select(
            DocumentRef.ordinal, DocumentRef.document_version_id,
        ).where(
            DocumentRef.reference_version_id == query.reference_version_id,
            DocumentRef.reference_solution_id == query.reference_solution_id,
            DocumentRef.scope == query.scope,
        ).order_by(DocumentRef.ordinal)).all())
        evidence = tuple(session.execute(select(
            EvidenceRef.ordinal, EvidenceRef.evidence_id,
        ).where(
            EvidenceRef.reference_version_id == query.reference_version_id,
            EvidenceRef.reference_solution_id == query.reference_solution_id,
            EvidenceRef.scope == query.scope,
        ).order_by(EvidenceRef.ordinal)).all())
        if (len(documents) != version.declared_document_count
                or len(evidence) != version.declared_evidence_count
                or tuple(item.ordinal for item in documents)
                != tuple(range(1, len(documents) + 1))
                or tuple(item.ordinal for item in evidence)
                != tuple(range(1, len(evidence) + 1))
                or not 1 <= len(documents) <= 100
                or len(evidence) > 500):
            return None
        return CurrentReferenceUseSnapshot(
            root.reference_solution_id, version.reference_version_id,
            root.scope, root.project_id, root.eligibility_state,
            event.eligibility_event_id, event.reference_version_id,
            event.result_state,
            tuple(item.document_version_id for item in documents),
            tuple(item.evidence_id for item in evidence),
            bytes(version.source_fingerprint),
            version.deidentification_confirmation_id,
        )


class SqlAlchemyCurrentGlobalConfirmationRepository:
    """Read only the latest confirmation; never authorizes GLOBAL browsing."""

    def current(self, transaction: object, *,
                current: CurrentReferenceUseSnapshot,
                now: datetime) -> CurrentGlobalConfirmationProof | None:
        if (type(current) is not CurrentReferenceUseSnapshot
                or current.scope != "GLOBAL"
                or current.source_project_id is not None
                or type(current.source_fingerprint) is not bytes
                or len(current.source_fingerprint) != 32
                or type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            return None
        row = _session(transaction).execute(select(Confirmation).where(
            Confirmation.source_fingerprint == current.source_fingerprint,
        ).order_by(
            Confirmation.confirmed_at.desc(),
            Confirmation.confirmation_id.desc(),
        ).limit(1).with_for_update(read=True, of=Confirmation)).scalar_one_or_none()
        if row is None:
            return None
        return CurrentGlobalConfirmationProof(
            row.confirmation_id, bytes(row.source_fingerprint),
            row.attestation_statement, row.confirmed_at, row.expires_at,
            row.revoked_at,
        )
