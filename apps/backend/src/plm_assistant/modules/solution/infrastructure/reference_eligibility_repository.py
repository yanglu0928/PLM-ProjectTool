"""Locked current Reference sources and event-backed human decision storage."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update

from plm_assistant.modules.solution.application.set_reference_eligibility import (
    LockedReferenceEligibility, ReferenceEligibilityResult,
)

from .orm import (
    ReferenceSolutionDocumentRefRow as DocumentRef,
    ReferenceSolutionEligibilityEventRow as Event,
    ReferenceSolutionEvidenceRefRow as EvidenceRef,
    ReferenceSolutionRow as Root,
    ReferenceSolutionVersionRow as Version,
)
from .reference_deidentification_repository import _session


class SqlAlchemyReferenceEligibilityRepository:
    def current(self, transaction: object, *, root_id: uuid.UUID, scope: str,
                project_id: uuid.UUID | None) -> LockedReferenceEligibility | None:
        if (type(root_id) is not uuid.UUID or root_id.int == 0
                or scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)):
            return None
        session = _session(transaction)
        root = session.execute(select(Root).where(
            Root.reference_solution_id == root_id,
            Root.scope == scope, Root.project_id == project_id,
        ).with_for_update(of=Root)).scalar_one_or_none()
        if root is None:
            return None
        version = session.execute(select(Version).where(
            Version.reference_version_id == root.current_version_ref,
            Version.reference_solution_id == root_id,
            Version.scope == scope, Version.project_id == project_id,
        ).with_for_update(read=True, of=Version)).scalar_one_or_none()
        if version is None or version.version_state != "DRAFT":
            raise RuntimeError("Reference current version is inconsistent")
        document_rows = tuple(session.execute(select(
            DocumentRef.ordinal, DocumentRef.document_version_id,
        ).where(
            DocumentRef.reference_version_id == version.reference_version_id,
            DocumentRef.reference_solution_id == root_id,
            DocumentRef.scope == scope,
        ).order_by(DocumentRef.ordinal)).all())
        evidence_rows = tuple(session.execute(select(
            EvidenceRef.ordinal, EvidenceRef.evidence_id,
        ).where(
            EvidenceRef.reference_version_id == version.reference_version_id,
            EvidenceRef.reference_solution_id == root_id,
            EvidenceRef.scope == scope,
        ).order_by(EvidenceRef.ordinal)).all())
        if (len(document_rows) != version.declared_document_count
                or len(evidence_rows) != version.declared_evidence_count
                or tuple(row.ordinal for row in document_rows)
                != tuple(range(1, len(document_rows)+1))
                or tuple(row.ordinal for row in evidence_rows)
                != tuple(range(1, len(evidence_rows)+1))
                or not 1 <= len(document_rows) <= 100
                or len(evidence_rows) > 500):
            raise RuntimeError("Reference fixed source set is inconsistent")
        return LockedReferenceEligibility(
            root.reference_solution_id, version.reference_version_id,
            scope, project_id, root.eligibility_state, root.lock_version,
            version.source_project_class, version.deidentification_class,
            dict(version.applicability),
            tuple(row.document_version_id for row in document_rows),
            tuple(row.evidence_id for row in evidence_rows),
            bytes(version.source_fingerprint),
            version.deidentification_confirmation_id,
        )

    def decide(self, transaction: object, *, current: LockedReferenceEligibility,
               actor_id: uuid.UUID, event_id: uuid.UUID, state: str,
               reason: str) -> ReferenceEligibilityResult:
        if (type(current) is not LockedReferenceEligibility
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(event_id) is not uuid.UUID or event_id.int == 0):
            raise ValueError("validated Reference decision required")
        session = _session(transaction)
        session.execute(insert(Event).values(
            eligibility_event_id=event_id,
            reference_solution_id=current.reference_solution_id,
            reference_version_id=current.reference_version_id,
            scope=current.scope, project_id=current.project_id,
            event_kind="HUMAN", prior_state=current.eligibility_state,
            result_state=state, reason=reason, actor_id=actor_id,
            prior_lock_version=current.lock_version,
            result_lock_version=current.lock_version+1,
        ))
        changed = session.execute(update(Root).where(
            Root.reference_solution_id == current.reference_solution_id,
            Root.scope == current.scope, Root.project_id == current.project_id,
            Root.current_version_ref == current.reference_version_id,
            Root.eligibility_state == current.eligibility_state,
            Root.lock_version == current.lock_version,
        ).values(eligibility_state=state, eligibility_reason=reason,
                 lock_version=current.lock_version+1)).rowcount
        if changed != 1:
            raise RuntimeError("Reference eligibility concurrency conflict")
        return ReferenceEligibilityResult(
            event_id, current.reference_solution_id, current.reference_version_id,
            current.scope, current.project_id, state, reason,
            current.lock_version+1,
        )

    def result(self, transaction: object, *, event_id: uuid.UUID, scope: str,
               project_id: uuid.UUID | None) -> ReferenceEligibilityResult | None:
        if type(event_id) is not uuid.UUID or event_id.int == 0:
            return None
        row = _session(transaction).execute(select(Event).where(
            Event.eligibility_event_id == event_id,
            Event.scope == scope, Event.project_id == project_id,
            Event.event_kind == "HUMAN",
        )).scalar_one_or_none()
        if row is None:
            return None
        return ReferenceEligibilityResult(
            row.eligibility_event_id, row.reference_solution_id,
            row.reference_version_id, row.scope, row.project_id,
            row.result_state, row.reason, row.result_lock_version,
        )
