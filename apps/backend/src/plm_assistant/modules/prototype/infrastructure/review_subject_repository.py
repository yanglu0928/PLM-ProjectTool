"""PostgreSQL Prototype Review Subject lock and formalization persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text, update

from plm_assistant.modules.prototype.application.review_subject import (
    PrototypeReviewLock,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)

from .orm import (
    PrototypeRow,
    PrototypeVersionReviewStateResultRow,
    PrototypeVersionRow,
)
from .version_read_repository import SqlAlchemyPrototypeVersionReadRepository


class SqlAlchemyPrototypeReviewSubjectRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemyPrototypeVersionReadRepository()

    def active_prototype_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID,
    ) -> bool:
        if not _ids(project_id, prototype_id):
            return False
        session = self._snapshots._session(transaction)
        found = session.execute(select(
            PrototypeRow.prototype_id,
        ).where(
            PrototypeRow.project_id == project_id,
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.prototype_state == "ACTIVE",
        ).with_for_update(read=True)).scalar_one_or_none()
        return found == prototype_id

    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID, prototype_version_id: uuid.UUID,
    ) -> PrototypeReviewLock | None:
        if not _ids(project_id, prototype_id, prototype_version_id):
            return None
        session = self._snapshots._session(transaction)
        prototype = session.execute(select(PrototypeRow).where(
            PrototypeRow.project_id == project_id,
            PrototypeRow.prototype_id == prototype_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(PrototypeVersionRow).where(
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.prototype_id == prototype_id,
            PrototypeVersionRow.prototype_version_id == prototype_version_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if prototype is None or version is None:
            return None
        snapshot = self._snapshots.get(
            transaction, project_id=project_id,
            prototype_id=prototype_id, version_id=prototype_version_id,
        )
        latest = session.execute(select(
            PrototypeVersionRow.prototype_version_id,
        ).where(
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.prototype_id == prototype_id,
        ).order_by(PrototypeVersionRow.version_no.desc()).limit(1)
        ).scalar_one_or_none()
        if snapshot is None or latest is None:
            return None
        return PrototypeReviewLock(
            snapshot, prototype.prototype_state, prototype.lock_version,
            prototype.current_approved_version_ref, latest,
            version.review_ref, version.review_round_ref,
        )

    def bind_start(
        self, transaction: object, *, before: PrototypeReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None:
        if (type(before) is not PrototypeReviewLock
                or not _ids(review_id, round_id, actor_id)):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        session, snapshot = self._snapshots._session(transaction), before.snapshot
        changed = session.execute(update(PrototypeVersionRow).where(
            PrototypeVersionRow.prototype_version_id
            == snapshot.prototype_version_id,
            PrototypeVersionRow.prototype_id == snapshot.prototype_id,
            PrototypeVersionRow.project_id == snapshot.project_id,
            PrototypeVersionRow.version_state == "DRAFT",
            PrototypeVersionRow.review_ref.is_(None),
            PrototypeVersionRow.review_round_ref.is_(None),
        ).values(
            version_state="IN_REVIEW", review_ref=review_id,
            review_round_ref=round_id,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        new_lock = before.prototype_lock_version + 1
        changed = session.execute(update(PrototypeRow).where(
            PrototypeRow.prototype_id == snapshot.prototype_id,
            PrototypeRow.project_id == snapshot.project_id,
            PrototypeRow.prototype_state == "ACTIVE",
            PrototypeRow.lock_version == before.prototype_lock_version,
            PrototypeRow.current_approved_version_ref.is_(None)
            if before.current_approved_version_ref is None else
            PrototypeRow.current_approved_version_ref
            == before.current_approved_version_ref,
        ).values(
            updated_by=actor_id, updated_at=text("statement_timestamp()"),
            lock_version=new_lock,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        session.add(PrototypeVersionReviewStateResultRow(
            prototype_version_id=snapshot.prototype_version_id,
            prototype_id=snapshot.prototype_id,
            project_id=snapshot.project_id,
            review_id=review_id, review_round_id=round_id,
            event_type="START",
            previous_approved_version_ref=before.current_approved_version_ref,
            current_approved_version_ref=before.current_approved_version_ref,
            actor_id=actor_id,
            expected_lock_version=before.prototype_lock_version,
            lock_version=new_lock,
        ))
        try:
            session.flush()
        except Exception:
            raise ReviewSubjectAccessDenied() from None

    def consume_terminal(
        self, transaction: object, *, before: PrototypeReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None:
        if (type(before) is not PrototypeReviewLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in {"APPROVED", "RETURNED"}):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        transition.__post_init__()
        snapshot = before.snapshot
        if (transition.before.subject_version_id
                != snapshot.prototype_version_id
                or transition.before.review.subject_id
                != snapshot.prototype_id
                or before.review_ref != transition.before.review.review_id
                or before.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = self._snapshots._session(transaction)
        previous = before.current_approved_version_ref
        if version_state == "APPROVED" and previous is not None:
            changed = session.execute(update(PrototypeVersionRow).where(
                PrototypeVersionRow.prototype_version_id == previous,
                PrototypeVersionRow.prototype_id == snapshot.prototype_id,
                PrototypeVersionRow.project_id == snapshot.project_id,
                PrototypeVersionRow.version_state == "APPROVED",
            ).values(version_state="SUPERSEDED"))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        changed = session.execute(update(PrototypeVersionRow).where(
            PrototypeVersionRow.prototype_version_id
            == snapshot.prototype_version_id,
            PrototypeVersionRow.prototype_id == snapshot.prototype_id,
            PrototypeVersionRow.project_id == snapshot.project_id,
            PrototypeVersionRow.version_state == "IN_REVIEW",
            PrototypeVersionRow.review_ref == before.review_ref,
            PrototypeVersionRow.review_round_ref == before.review_round_ref,
        ).values(version_state=version_state))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        current = (snapshot.prototype_version_id
                   if version_state == "APPROVED" else previous)
        new_lock = before.prototype_lock_version + 1
        values = {
            "updated_by": transition.actor_id,
            "updated_at": text("statement_timestamp()"),
            "lock_version": new_lock,
        }
        if version_state == "APPROVED":
            values["current_approved_version_ref"] = current
        changed = session.execute(update(PrototypeRow).where(
            PrototypeRow.prototype_id == snapshot.prototype_id,
            PrototypeRow.project_id == snapshot.project_id,
            PrototypeRow.prototype_state == "ACTIVE",
            PrototypeRow.lock_version == before.prototype_lock_version,
            PrototypeRow.current_approved_version_ref.is_(None)
            if previous is None else
            PrototypeRow.current_approved_version_ref == previous,
        ).values(**values))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        session.add(PrototypeVersionReviewStateResultRow(
            prototype_version_id=snapshot.prototype_version_id,
            prototype_id=snapshot.prototype_id,
            project_id=snapshot.project_id,
            review_id=transition.before.review.review_id,
            review_round_id=transition.before.progress.round_id,
            event_type=transition.after_progress.state.value,
            previous_approved_version_ref=previous,
            current_approved_version_ref=current,
            actor_id=transition.actor_id,
            expected_lock_version=before.prototype_lock_version,
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
                or version_state not in {"APPROVED", "RETURNED"}):
            raise ReviewSubjectAccessDenied()
        transition.__post_init__()
        session = self._snapshots._session(transaction)
        prototype_id = transition.before.review.subject_id
        project_id = transition.before.review.project_id
        version_id = transition.before.subject_version_id
        review_id = transition.before.review.review_id
        round_id = transition.before.progress.round_id
        event = transition.after_progress.state.value
        prototype = session.execute(select(PrototypeRow).where(
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.project_id == project_id,
            PrototypeRow.prototype_state == "ACTIVE",
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(PrototypeVersionRow).where(
            PrototypeVersionRow.prototype_version_id == version_id,
            PrototypeVersionRow.prototype_id == prototype_id,
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.version_state == version_state,
            PrototypeVersionRow.review_ref == review_id,
            PrototypeVersionRow.review_round_ref == round_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        result = session.execute(select(
            PrototypeVersionReviewStateResultRow,
        ).where(
            PrototypeVersionReviewStateResultRow.prototype_version_id
            == version_id,
            PrototypeVersionReviewStateResultRow.prototype_id == prototype_id,
            PrototypeVersionReviewStateResultRow.project_id == project_id,
            PrototypeVersionReviewStateResultRow.review_id == review_id,
            PrototypeVersionReviewStateResultRow.review_round_id == round_id,
            PrototypeVersionReviewStateResultRow.event_type == event,
            PrototypeVersionReviewStateResultRow.actor_id
            == transition.actor_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        approved_count = session.execute(select(func.count()).select_from(
            PrototypeVersionRow,
        ).where(
            PrototypeVersionRow.prototype_id == prototype_id,
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.version_state == "APPROVED",
        )).scalar_one()
        if prototype is None or version is None or result is None:
            raise ReviewSubjectAccessDenied()
        if (result.lock_version != prototype.lock_version
                or result.expected_lock_version + 1 != result.lock_version
                or result.current_approved_version_ref
                != prototype.current_approved_version_ref):
            raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            valid = (prototype.current_approved_version_ref == version_id
                     and result.previous_approved_version_ref
                     != result.current_approved_version_ref
                     and approved_count == 1)
        else:
            valid = (prototype.current_approved_version_ref != version_id
                     and result.previous_approved_version_ref
                     == result.current_approved_version_ref
                     and approved_count == (
                         0 if prototype.current_approved_version_ref is None
                         else 1))
        if not valid:
            raise ReviewSubjectAccessDenied()


def _ids(*values: object) -> bool:
    return all(type(value) is uuid.UUID and value.int != 0
               for value in values)
