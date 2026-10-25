"""Same-transaction PlanVersion Review binding required by Migration 0190."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update

from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanVersionReviewLock,
)
from plm_assistant.modules.plan.infrastructure.create_repository import _session
from plm_assistant.modules.plan.infrastructure.orm import (
    PlanRow, PlanVersionReviewStateResultRow, PlanVersionRow,
)
from plm_assistant.modules.plan.infrastructure.plan_review_readiness_repository import (
    SqlAlchemyPlanVersionReviewReadinessRepository,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)


def _ids(*values: object) -> bool:
    return all(type(value) is uuid.UUID and value.int != 0 for value in values)


class SqlAlchemyPlanReviewSubjectRepository:
    """Locks the Plan identity before its version set, then binds START."""

    def __init__(self) -> None:
        self._readiness = SqlAlchemyPlanVersionReviewReadinessRepository()

    def lock_subject(self, tx, *, project_id, plan_version_id):
        if not _ids(project_id, plan_version_id):
            return None
        session = _session(tx)
        plan_id = session.execute(select(PlanVersionRow.plan_id).where(
            PlanVersionRow.project_id == project_id,
            PlanVersionRow.plan_version_id == plan_version_id,
        )).scalar_one_or_none()
        if plan_id is None:
            return None
        return self._readiness.lock_current(
            tx, project_id=project_id, plan_id=plan_id,
            plan_version_id=plan_version_id)

    def version_exists(self, tx, *, project_id, plan_version_id) -> bool:
        if not _ids(project_id, plan_version_id):
            return False
        return _session(tx).execute(select(PlanVersionRow.plan_version_id).where(
            PlanVersionRow.project_id == project_id,
            PlanVersionRow.plan_version_id == plan_version_id,
        )).scalar_one_or_none() == plan_version_id

    def version_belongs_to_plan(self, tx, *, project_id, plan_id,
                                plan_version_id) -> bool:
        if not _ids(project_id, plan_id, plan_version_id):
            return False
        return _session(tx).execute(select(PlanVersionRow.plan_version_id).where(
            PlanVersionRow.project_id == project_id,
            PlanVersionRow.plan_id == plan_id,
            PlanVersionRow.plan_version_id == plan_version_id,
        )).scalar_one_or_none() == plan_version_id

    def bind_start(self, tx, *, before: PlanVersionReviewLock,
                   review_id, round_id, actor_id) -> None:
        if (type(before) is not PlanVersionReviewLock
                or not _ids(review_id, round_id, actor_id)):
            raise ReviewSubjectAccessDenied()
        version = before.snapshot
        if (version.version_state != "DRAFT"
                or before.latest_version_id != version.plan_version_id
                or version.review_ref is not None
                or version.review_round_ref is not None):
            raise ReviewSubjectAccessDenied()
        session = _session(tx)
        changed = session.execute(update(PlanVersionRow).where(
            PlanVersionRow.plan_version_id == version.plan_version_id,
            PlanVersionRow.plan_id == version.plan_id,
            PlanVersionRow.project_id == version.project_id,
            PlanVersionRow.version_state == "DRAFT",
            PlanVersionRow.review_ref.is_(None),
            PlanVersionRow.review_round_ref.is_(None),
        ).values(version_state="IN_REVIEW", review_ref=review_id,
                 review_round_ref=round_id).execution_options(
                     synchronize_session=False))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        session.add(PlanVersionReviewStateResultRow(
            plan_version_id=version.plan_version_id,
            plan_id=version.plan_id, project_id=version.project_id,
            review_id=review_id, review_round_id=round_id,
            event_type="START", previous_state="DRAFT",
            current_state="IN_REVIEW", actor_id=actor_id,
        ))
        try:
            session.flush()
        except Exception:
            raise ReviewSubjectAccessDenied() from None

    def lock_terminal_subject(self, tx, *, project_id, plan_id,
                              plan_version_id):
        """Lock Plan identity and all versions, then reconstruct the fixed subject."""
        if (not _ids(project_id, plan_version_id)
                or plan_id is not None and not _ids(plan_id)):
            return None
        session = _session(tx)
        if plan_id is None:
            plan_id = session.execute(select(PlanVersionRow.plan_id).where(
                PlanVersionRow.project_id == project_id,
                PlanVersionRow.plan_version_id == plan_version_id,
            )).scalar_one_or_none()
            if plan_id is None:
                return None
        locked = self._readiness.lock_current(
            tx, project_id=project_id, plan_id=plan_id,
            plan_version_id=plan_version_id)
        if locked is None:
            return None
        plan = session.execute(select(PlanRow).where(
            PlanRow.project_id == project_id,
            PlanRow.plan_id == plan_id,
        ).with_for_update(of=PlanRow).execution_options(
            populate_existing=True)).scalar_one_or_none()
        if plan is None:
            return None
        from plm_assistant.modules.plan.application.plan_version_review_terminal import (
            PlanReviewTerminalLock,
        )
        return PlanReviewTerminalLock(
            locked.snapshot, locked.latest_version_id,
            plan.current_approved_version_ref)

    def consume_terminal(self, tx, *, before, transition, version_state,
                         event_type):
        from plm_assistant.modules.plan.application.plan_version_review_terminal import (
            PlanReviewTerminalLock,
        )
        from plm_assistant.modules.review.application.subject_transition import (
            ReviewSubjectTransition,
        )
        if (type(before) is not PlanReviewTerminalLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")
                or event_type not in ("APPROVED", "RETURNED", "WITHDRAWN")):
            raise ReviewSubjectAccessDenied()
        snapshot = before.snapshot
        session = _session(tx)
        current = self.lock_terminal_subject(
            tx, project_id=snapshot.project_id, plan_id=snapshot.plan_id,
            plan_version_id=snapshot.plan_version_id)
        if current != before or snapshot.version_state != "IN_REVIEW":
            raise ReviewSubjectAccessDenied()

        superseded = None
        if version_state == "APPROVED" and before.current_approved_version_ref is not None:
            if before.current_approved_version_ref == snapshot.plan_version_id:
                raise ReviewSubjectAccessDenied()
            old = session.execute(select(PlanVersionRow).where(
                PlanVersionRow.plan_version_id == before.current_approved_version_ref,
                PlanVersionRow.plan_id == snapshot.plan_id,
                PlanVersionRow.project_id == snapshot.project_id,
                PlanVersionRow.version_state == "APPROVED",
            ).with_for_update()).scalar_one_or_none()
            if (old is None or old.review_ref is None
                    or old.review_round_ref is None):
                raise ReviewSubjectAccessDenied()
            approved_result = session.execute(select(
                PlanVersionReviewStateResultRow).where(
                    PlanVersionReviewStateResultRow.plan_version_id == old.plan_version_id,
                    PlanVersionReviewStateResultRow.plan_id == old.plan_id,
                    PlanVersionReviewStateResultRow.project_id == old.project_id,
                    PlanVersionReviewStateResultRow.event_type == "APPROVED",
                    PlanVersionReviewStateResultRow.review_id == old.review_ref,
                    PlanVersionReviewStateResultRow.review_round_id == old.review_round_ref,
            )).scalar_one_or_none()
            if approved_result is None:
                raise ReviewSubjectAccessDenied()
            changed = session.execute(update(PlanVersionRow).where(
                PlanVersionRow.plan_version_id == old.plan_version_id,
                PlanVersionRow.plan_id == old.plan_id,
                PlanVersionRow.project_id == old.project_id,
                PlanVersionRow.version_state == "APPROVED",
            ).values(version_state="SUPERSEDED").execution_options(
                synchronize_session=False))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
            superseded = PlanVersionReviewStateResultRow(
                plan_version_id=old.plan_version_id, plan_id=old.plan_id,
                project_id=old.project_id, review_id=old.review_ref,
                review_round_id=old.review_round_ref,
                event_type="SUPERSEDED", previous_state="APPROVED",
                current_state="SUPERSEDED", actor_id=approved_result.actor_id)
            session.add(superseded)

        changed = session.execute(update(PlanVersionRow).where(
            PlanVersionRow.plan_version_id == snapshot.plan_version_id,
            PlanVersionRow.plan_id == snapshot.plan_id,
            PlanVersionRow.project_id == snapshot.project_id,
            PlanVersionRow.version_state == "IN_REVIEW",
            PlanVersionRow.review_ref == transition.before.review.review_id,
            PlanVersionRow.review_round_ref == transition.before.progress.round_id,
        ).values(version_state=version_state).execution_options(
            synchronize_session=False))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        result = PlanVersionReviewStateResultRow(
            plan_version_id=snapshot.plan_version_id,
            plan_id=snapshot.plan_id, project_id=snapshot.project_id,
            review_id=transition.before.review.review_id,
            review_round_id=transition.before.progress.round_id,
            event_type=event_type, previous_state="IN_REVIEW",
            current_state=version_state, actor_id=transition.actor_id)
        session.add(result)
        session.flush()
        if version_state == "APPROVED":
            changed = session.execute(update(PlanRow).where(
                PlanRow.plan_id == snapshot.plan_id,
                PlanRow.project_id == snapshot.project_id,
                PlanRow.current_approved_version_ref ==
                    before.current_approved_version_ref,
                PlanRow.lock_version < 2**63 - 1,
            ).values(current_approved_version_ref=snapshot.plan_version_id,
                     lock_version=PlanRow.lock_version + 1).execution_options(
                         synchronize_session=False))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        session.flush()
        result_id = result.review_state_result_id
        if result_id is None:
            result_id = session.execute(select(
                PlanVersionReviewStateResultRow.review_state_result_id).where(
                    PlanVersionReviewStateResultRow.plan_version_id == snapshot.plan_version_id,
                    PlanVersionReviewStateResultRow.event_type == event_type,
            )).scalar_one_or_none()
        if not _ids(result_id):
            raise ReviewSubjectAccessDenied()
        return result_id

    def assert_terminal_consumed(self, tx, *, transition, version_state,
                                 event_type):
        from plm_assistant.modules.review.application.subject_transition import (
            ReviewSubjectTransition,
        )
        if (type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")
                or event_type not in ("APPROVED", "RETURNED", "WITHDRAWN")):
            raise ReviewSubjectAccessDenied()
        session = _session(tx)
        plan_id = self._plan_id_for_version(
            tx, transition.before.subject_version_id)
        if plan_id is None:
            raise ReviewSubjectAccessDenied()
        locked = self.lock_terminal_subject(
            tx, project_id=transition.before.review.project_id,
            plan_id=plan_id,
            plan_version_id=transition.before.subject_version_id)
        snapshot = None if locked is None else locked.snapshot
        if (snapshot is None or snapshot.version_state != version_state
                or snapshot.review_ref != transition.before.review.review_id
                or snapshot.review_round_ref != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        result = session.execute(select(PlanVersionReviewStateResultRow).where(
            PlanVersionReviewStateResultRow.plan_version_id == snapshot.plan_version_id,
            PlanVersionReviewStateResultRow.plan_id == snapshot.plan_id,
            PlanVersionReviewStateResultRow.project_id == snapshot.project_id,
            PlanVersionReviewStateResultRow.review_id == transition.before.review.review_id,
            PlanVersionReviewStateResultRow.review_round_id == transition.before.progress.round_id,
            PlanVersionReviewStateResultRow.event_type == event_type,
            PlanVersionReviewStateResultRow.previous_state == "IN_REVIEW",
            PlanVersionReviewStateResultRow.current_state == version_state,
            PlanVersionReviewStateResultRow.actor_id == transition.actor_id,
        )).scalar_one_or_none()
        plan = session.execute(select(PlanRow).where(
            PlanRow.plan_id == snapshot.plan_id,
            PlanRow.project_id == snapshot.project_id,
        )).scalar_one_or_none()
        if result is None or plan is None:
            raise ReviewSubjectAccessDenied()
        approved = tuple(session.execute(select(
            PlanVersionRow.plan_version_id).where(
                PlanVersionRow.plan_id == snapshot.plan_id,
                PlanVersionRow.project_id == snapshot.project_id,
                PlanVersionRow.version_state == "APPROVED",
        )).scalars())
        expected_pointer = (snapshot.plan_version_id
                            if version_state == "APPROVED" else
                            (approved[0] if approved else None))
        if (len(approved) > 1
                or plan.current_approved_version_ref != expected_pointer):
            raise ReviewSubjectAccessDenied()
        if (version_state != "APPROVED" and locked.current_approved_version_ref
                != expected_pointer):
            raise ReviewSubjectAccessDenied()
        return result.review_state_result_id

    @staticmethod
    def _plan_id_for_version(tx, plan_version_id):
        session = _session(tx)
        return session.execute(select(PlanVersionRow.plan_id).where(
            PlanVersionRow.plan_version_id == plan_version_id,
        )).scalar_one_or_none()
