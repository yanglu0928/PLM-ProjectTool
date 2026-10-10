"""Root-serialized GLOBAL publication history; no project-facing read projection."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select

from plm_assistant.modules.solution.application.set_global_reference_publication import (
    GlobalReferencePublicationResult, LockedGlobalPublicationTarget,
    SetGlobalReferencePublication,
)

from .orm import (
    GlobalReferencePublicationEventRow as Publication,
    ReferenceSolutionEligibilityEventRow as Eligibility,
)
from .reference_deidentification_repository import _session
from .reference_eligibility_repository import SqlAlchemyReferenceEligibilityRepository


class SqlAlchemyGlobalReferencePublicationRepository:
    def __init__(self) -> None:
        self._references = SqlAlchemyReferenceEligibilityRepository()

    def current(self, transaction: object, *, root_id: uuid.UUID
                ) -> LockedGlobalPublicationTarget | None:
        if type(root_id) is not uuid.UUID or root_id.int == 0:
            return None
        reference = self._references.current(
            transaction, root_id=root_id, scope="GLOBAL", project_id=None)
        if reference is None:
            return None
        session = _session(transaction)
        eligibility = session.execute(select(Eligibility).where(
            Eligibility.reference_solution_id == root_id,
        ).order_by(Eligibility.result_lock_version.desc()).limit(1).with_for_update(
            read=True, of=Eligibility)).scalar_one_or_none()
        eligible_current = (
            eligibility is not None
            and eligibility.scope == "GLOBAL"
            and eligibility.project_id is None
            and eligibility.event_kind == "HUMAN"
            and eligibility.reference_version_id == reference.reference_version_id
            and eligibility.result_state == "ELIGIBLE"
            and eligibility.result_lock_version == reference.lock_version
        )
        latest = session.execute(select(Publication).where(
            Publication.reference_solution_id == root_id,
        ).order_by(Publication.event_no.desc()).limit(1)).scalar_one_or_none()
        if latest is not None and (
                latest.scope != "GLOBAL" or latest.event_no <= 0
                or latest.event_kind not in ("PUBLISH", "REVOKE")):
            raise RuntimeError("GLOBAL publication history is inconsistent")
        return LockedGlobalPublicationTarget(
            reference, eligible_current,
            latest.event_no if latest else 0,
            latest.event_kind if latest else None,
            latest.reference_version_id if latest else None,
        )

    def append(self, transaction: object, *, current: LockedGlobalPublicationTarget,
               event_id: uuid.UUID, actor_id: uuid.UUID,
               command: SetGlobalReferencePublication
               ) -> GlobalReferencePublicationResult:
        if (type(current) is not LockedGlobalPublicationTarget
                or type(event_id) is not uuid.UUID or event_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(command) is not SetGlobalReferencePublication):
            raise ValueError("validated GLOBAL publication required")
        row = _session(transaction).execute(insert(Publication).values(
            publication_event_id=event_id,
            reference_solution_id=current.reference.reference_solution_id,
            reference_version_id=current.reference.reference_version_id,
            scope="GLOBAL", event_no=current.latest_event_no + 1,
            event_kind=command.event_kind, display_label=command.display_label,
            reason=command.reason, actor_id=actor_id,
        ).returning(Publication)).scalar_one()
        return self._view(row)

    def result(self, transaction: object, *, event_id: uuid.UUID,
               root_id: uuid.UUID) -> GlobalReferencePublicationResult | None:
        if (type(event_id) is not uuid.UUID or event_id.int == 0
                or type(root_id) is not uuid.UUID or root_id.int == 0):
            return None
        row = _session(transaction).execute(select(Publication).where(
            Publication.publication_event_id == event_id,
            Publication.reference_solution_id == root_id,
            Publication.scope == "GLOBAL",
        )).scalar_one_or_none()
        return self._view(row) if row is not None else None

    @staticmethod
    def _view(row: Publication) -> GlobalReferencePublicationResult:
        return GlobalReferencePublicationResult(
            row.publication_event_id, row.reference_solution_id,
            row.reference_version_id, row.event_no, row.event_kind,
            row.display_label, row.reason, row.created_at,
        )
