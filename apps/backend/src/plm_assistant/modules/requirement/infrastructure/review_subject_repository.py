"""PostgreSQL Requirement Review Subject lock and formalization persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text, update

from plm_assistant.modules.requirement.application.review_subject import (
    RequirementReviewLock,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)

from .identity_create_repository import _session
from .orm import (
    RequirementReviewStateResultRow, RequirementRow, RequirementVersionRow,
)
from .version_validation_repository import (
    SqlAlchemyRequirementVersionValidationRepository,
)


class SqlAlchemyRequirementReviewSubjectRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemyRequirementVersionValidationRepository()

    def active_requirement_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID,
    ) -> bool:
        if not self._ids(project_id, requirement_id):
            return False
        found = _session(transaction).execute(select(
            RequirementRow.requirement_id,
        ).where(
            RequirementRow.project_id == project_id,
            RequirementRow.requirement_id == requirement_id,
            RequirementRow.requirement_state == "ACTIVE",
        ).with_for_update(read=True)).scalar_one_or_none()
        return found == requirement_id

    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> RequirementReviewLock | None:
        if not self._ids(project_id, requirement_id, requirement_version_id):
            return None
        session = _session(transaction)
        requirement = session.execute(select(RequirementRow).where(
            RequirementRow.project_id == project_id,
            RequirementRow.requirement_id == requirement_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(RequirementVersionRow).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.requirement_version_id
            == requirement_version_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if requirement is None or version is None:
            return None
        snapshot = self._snapshots.lock_snapshot(
            transaction, project_id=project_id,
            requirement_id=requirement_id,
            requirement_version_id=requirement_version_id,
        )
        latest = session.execute(select(
            RequirementVersionRow.requirement_version_id,
        ).where(
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.project_id == project_id,
        ).order_by(RequirementVersionRow.version_no.desc()).limit(1)
        ).scalar_one_or_none()
        if snapshot is None or latest is None:
            return None
        return RequirementReviewLock(
            snapshot, requirement.requirement_state,
            requirement.lock_version,
            requirement.current_approved_version_ref, latest,
            version.review_ref, version.review_round_ref,
        )

    def bind_start(
        self, transaction: object, *, before: RequirementReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None:
        if (type(before) is not RequirementReviewLock
                or not self._ids(review_id, round_id, actor_id)):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        session, snapshot = _session(transaction), before.snapshot
        changed = session.execute(update(RequirementVersionRow).where(
            RequirementVersionRow.requirement_version_id
            == snapshot.requirement_version_id,
            RequirementVersionRow.requirement_id == snapshot.requirement_id,
            RequirementVersionRow.project_id == snapshot.project_id,
            RequirementVersionRow.version_state == "DRAFT",
            RequirementVersionRow.review_ref.is_(None),
            RequirementVersionRow.review_round_ref.is_(None),
        ).values(
            version_state="IN_REVIEW", review_ref=review_id,
            review_round_ref=round_id,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        new_lock = before.requirement_lock_version + 1
        changed = session.execute(update(RequirementRow).where(
            RequirementRow.requirement_id == snapshot.requirement_id,
            RequirementRow.project_id == snapshot.project_id,
            RequirementRow.requirement_state == "ACTIVE",
            RequirementRow.lock_version == before.requirement_lock_version,
            RequirementRow.current_approved_version_ref.is_(None)
            if before.current_approved_version_ref is None else
            RequirementRow.current_approved_version_ref
            == before.current_approved_version_ref,
        ).values(
            updated_by=actor_id, updated_at=text("statement_timestamp()"),
            lock_version=new_lock,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        session.add(RequirementReviewStateResultRow(
            requirement_version_id=snapshot.requirement_version_id,
            requirement_id=snapshot.requirement_id,
            project_id=snapshot.project_id,
            review_id=review_id,
            review_round_id=round_id,
            event_type="START",
            previous_approved_version_ref=before.current_approved_version_ref,
            current_approved_version_ref=before.current_approved_version_ref,
            actor_id=actor_id,
            expected_lock_version=before.requirement_lock_version,
            lock_version=new_lock,
        ))
        try:
            session.flush()
        except Exception:
            raise ReviewSubjectAccessDenied() from None

    def consume_terminal(
        self, transaction: object, *, before: RequirementReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None:
        if (type(before) is not RequirementReviewLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        transition.__post_init__()
        snapshot = before.snapshot
        if (transition.before.subject_version_id
                != snapshot.requirement_version_id
                or transition.before.review.subject_id
                != snapshot.requirement_id
                or before.review_ref != transition.before.review.review_id
                or before.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        previous = before.current_approved_version_ref
        if version_state == "APPROVED" and previous is not None:
            changed = session.execute(update(RequirementVersionRow).where(
                RequirementVersionRow.requirement_version_id == previous,
                RequirementVersionRow.requirement_id
                == snapshot.requirement_id,
                RequirementVersionRow.project_id == snapshot.project_id,
                RequirementVersionRow.version_state == "APPROVED",
            ).values(version_state="SUPERSEDED"))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        changed = session.execute(update(RequirementVersionRow).where(
            RequirementVersionRow.requirement_version_id
            == snapshot.requirement_version_id,
            RequirementVersionRow.requirement_id == snapshot.requirement_id,
            RequirementVersionRow.project_id == snapshot.project_id,
            RequirementVersionRow.version_state == "IN_REVIEW",
            RequirementVersionRow.review_ref == before.review_ref,
            RequirementVersionRow.review_round_ref == before.review_round_ref,
        ).values(version_state=version_state))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        current = (snapshot.requirement_version_id
                   if version_state == "APPROVED" else previous)
        new_lock = before.requirement_lock_version + 1
        values = {
            "updated_by": transition.actor_id,
            "updated_at": text("statement_timestamp()"),
            "lock_version": new_lock,
        }
        if version_state == "APPROVED":
            values["current_approved_version_ref"] = current
        changed = session.execute(update(RequirementRow).where(
            RequirementRow.requirement_id == snapshot.requirement_id,
            RequirementRow.project_id == snapshot.project_id,
            RequirementRow.requirement_state == "ACTIVE",
            RequirementRow.lock_version == before.requirement_lock_version,
            RequirementRow.current_approved_version_ref.is_(None)
            if previous is None else
            RequirementRow.current_approved_version_ref == previous,
        ).values(**values))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        session.add(RequirementReviewStateResultRow(
            requirement_version_id=snapshot.requirement_version_id,
            requirement_id=snapshot.requirement_id,
            project_id=snapshot.project_id,
            review_id=transition.before.review.review_id,
            review_round_id=transition.before.progress.round_id,
            event_type=transition.after_progress.state.value,
            previous_approved_version_ref=previous,
            current_approved_version_ref=current,
            actor_id=transition.actor_id,
            expected_lock_version=before.requirement_lock_version,
            lock_version=new_lock,
        ))
        try:
            session.flush()
        except Exception:
            raise ReviewSubjectAccessDenied() from None

    def assert_terminal_consumed(
        self, transaction: object, *, transition: ReviewSubjectTransition,
        version_state: str,
    ) -> None:
        if (type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        transition.__post_init__()
        session = _session(transaction)
        requirement_id = transition.before.review.subject_id
        project_id = transition.before.review.project_id
        version_id = transition.before.subject_version_id
        review_id = transition.before.review.review_id
        round_id = transition.before.progress.round_id
        event = transition.after_progress.state.value
        requirement = session.execute(select(RequirementRow).where(
            RequirementRow.requirement_id == requirement_id,
            RequirementRow.project_id == project_id,
            RequirementRow.requirement_state == "ACTIVE",
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(RequirementVersionRow).where(
            RequirementVersionRow.requirement_version_id == version_id,
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.version_state == version_state,
            RequirementVersionRow.review_ref == review_id,
            RequirementVersionRow.review_round_ref == round_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        result = session.execute(select(
            RequirementReviewStateResultRow,
        ).where(
            RequirementReviewStateResultRow.requirement_version_id
            == version_id,
            RequirementReviewStateResultRow.requirement_id == requirement_id,
            RequirementReviewStateResultRow.project_id == project_id,
            RequirementReviewStateResultRow.review_id == review_id,
            RequirementReviewStateResultRow.review_round_id == round_id,
            RequirementReviewStateResultRow.event_type == event,
            RequirementReviewStateResultRow.actor_id == transition.actor_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        approved_count = session.execute(select(func.count()).select_from(
            RequirementVersionRow,
        ).where(
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.version_state == "APPROVED",
        )).scalar_one()
        if requirement is None or version is None or result is None:
            raise ReviewSubjectAccessDenied()
        if (result.lock_version != requirement.lock_version
                or result.expected_lock_version + 1 != result.lock_version
                or result.current_approved_version_ref
                != requirement.current_approved_version_ref):
            raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            valid = (requirement.current_approved_version_ref == version_id
                     and result.previous_approved_version_ref
                     != result.current_approved_version_ref
                     and approved_count == 1)
        else:
            valid = (requirement.current_approved_version_ref != version_id
                     and result.previous_approved_version_ref
                     == result.current_approved_version_ref
                     and approved_count == (
                         0 if requirement.current_approved_version_ref is None
                         else 1))
        if not valid:
            raise ReviewSubjectAccessDenied()

    @staticmethod
    def _ids(*values):
        return all(type(value) is uuid.UUID and value.int != 0
                   for value in values)
