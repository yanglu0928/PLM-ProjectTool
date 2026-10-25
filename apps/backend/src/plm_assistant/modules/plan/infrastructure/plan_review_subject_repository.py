"""Same-transaction PlanVersion Review binding required by Migration 0190."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update

from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanVersionReviewLock,
)
from plm_assistant.modules.plan.infrastructure.create_repository import _session
from plm_assistant.modules.plan.infrastructure.orm import (
    PlanVersionReviewStateResultRow, PlanVersionRow,
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
