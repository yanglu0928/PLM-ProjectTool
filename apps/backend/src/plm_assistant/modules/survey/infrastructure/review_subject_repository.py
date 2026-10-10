"""PostgreSQL Survey Review Subject lock and formalization persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text, update

from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.survey.application.review_subject import (
    SurveyReviewLock,
)

from .orm import SurveyRow, SurveyVersionRow
from .survey_create_repository import _session
from .version_validation_repository import (
    SqlAlchemySurveyVersionValidationRepository,
)


class SqlAlchemySurveyReviewSubjectRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemySurveyVersionValidationRepository()

    def active_survey_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_id: uuid.UUID,
    ) -> bool:
        if not self._ids(project_id, survey_id):
            return False
        found = _session(transaction).execute(select(
            SurveyRow.survey_id,
        ).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == survey_id,
            SurveyRow.survey_state == "ACTIVE",
        ).with_for_update(read=True)).scalar_one_or_none()
        return found == survey_id

    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_id: uuid.UUID, survey_version_id: uuid.UUID,
    ) -> SurveyReviewLock | None:
        if not self._ids(project_id, survey_id, survey_version_id):
            return None
        session = _session(transaction)
        survey = session.execute(select(SurveyRow).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == survey_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(SurveyVersionRow).where(
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.survey_version_id == survey_version_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if survey is None or version is None:
            return None
        snapshot = self._snapshots.lock_snapshot(
            transaction, project_id=project_id, survey_id=survey_id,
            survey_version_id=survey_version_id,
        )
        latest = session.execute(select(
            SurveyVersionRow.survey_version_id,
        ).where(
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.project_id == project_id,
        ).order_by(SurveyVersionRow.version_no.desc()).limit(1)
        ).scalar_one_or_none()
        if snapshot is None or latest is None:
            return None
        return SurveyReviewLock(
            snapshot, survey.survey_state, survey.lock_version,
            survey.current_approved_version_ref, latest,
            version.review_ref, version.review_round_ref,
        )

    def bind_start(
        self, transaction: object, *, before: SurveyReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None:
        if (type(before) is not SurveyReviewLock
                or not self._ids(review_id, round_id, actor_id)):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        session, snapshot = _session(transaction), before.snapshot
        changed = session.execute(update(SurveyVersionRow).where(
            SurveyVersionRow.survey_version_id == snapshot.survey_version_id,
            SurveyVersionRow.survey_id == snapshot.survey_id,
            SurveyVersionRow.project_id == snapshot.project_id,
            SurveyVersionRow.version_state == "DRAFT",
            SurveyVersionRow.review_ref.is_(None),
            SurveyVersionRow.review_round_ref.is_(None),
        ).values(
            version_state="IN_REVIEW", review_ref=review_id,
            review_round_ref=round_id,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        changed = session.execute(update(SurveyRow).where(
            SurveyRow.survey_id == snapshot.survey_id,
            SurveyRow.project_id == snapshot.project_id,
            SurveyRow.survey_state == "ACTIVE",
            SurveyRow.lock_version == before.survey_lock_version,
        ).values(
            updated_by=actor_id, updated_at=text("statement_timestamp()"),
            lock_version=SurveyRow.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()

    def consume_terminal(
        self, transaction: object, *, before: SurveyReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None:
        if (type(before) is not SurveyReviewLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        transition.__post_init__()
        snapshot = before.snapshot
        if (transition.before.subject_version_id != snapshot.survey_version_id
                or transition.before.review.subject_id != snapshot.survey_id
                or before.review_ref != transition.before.review.review_id
                or before.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        previous = before.current_approved_version_ref
        if version_state == "APPROVED" and previous is not None:
            changed = session.execute(update(SurveyVersionRow).where(
                SurveyVersionRow.survey_version_id == previous,
                SurveyVersionRow.survey_id == snapshot.survey_id,
                SurveyVersionRow.project_id == snapshot.project_id,
                SurveyVersionRow.version_state == "APPROVED",
            ).values(version_state="SUPERSEDED"))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        changed = session.execute(update(SurveyVersionRow).where(
            SurveyVersionRow.survey_version_id == snapshot.survey_version_id,
            SurveyVersionRow.survey_id == snapshot.survey_id,
            SurveyVersionRow.project_id == snapshot.project_id,
            SurveyVersionRow.version_state == "IN_REVIEW",
            SurveyVersionRow.review_ref == before.review_ref,
            SurveyVersionRow.review_round_ref == before.review_round_ref,
        ).values(version_state=version_state))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        values = {
            "updated_by": transition.actor_id,
            "updated_at": text("statement_timestamp()"),
            "lock_version": SurveyRow.lock_version + 1,
        }
        if version_state == "APPROVED":
            values["current_approved_version_ref"] = snapshot.survey_version_id
        changed = session.execute(update(SurveyRow).where(
            SurveyRow.survey_id == snapshot.survey_id,
            SurveyRow.project_id == snapshot.project_id,
            SurveyRow.survey_state == "ACTIVE",
            SurveyRow.lock_version == before.survey_lock_version,
            SurveyRow.current_approved_version_ref.is_(None)
            if previous is None else
            SurveyRow.current_approved_version_ref == previous,
        ).values(**values))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()

    def assert_terminal_consumed(
        self, transaction: object, *, transition: ReviewSubjectTransition,
        version_state: str,
    ) -> None:
        if (type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        transition.__post_init__()
        session = _session(transaction)
        survey_id = transition.before.review.subject_id
        project_id = transition.before.review.project_id
        version_id = transition.before.subject_version_id
        survey = session.execute(select(SurveyRow).where(
            SurveyRow.survey_id == survey_id,
            SurveyRow.project_id == project_id,
            SurveyRow.survey_state == "ACTIVE",
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(SurveyVersionRow).where(
            SurveyVersionRow.survey_version_id == version_id,
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.version_state == version_state,
            SurveyVersionRow.review_ref == transition.before.review.review_id,
            SurveyVersionRow.review_round_ref
            == transition.before.progress.round_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        approved_count = session.execute(select(func.count()).select_from(
            SurveyVersionRow,
        ).where(
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.version_state == "APPROVED",
        )).scalar_one()
        if survey is None or version is None:
            raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            valid = (survey.current_approved_version_ref == version_id
                     and approved_count == 1)
        else:
            valid = (survey.current_approved_version_ref != version_id
                     and approved_count == (
                         0 if survey.current_approved_version_ref is None else 1))
        if not valid:
            raise ReviewSubjectAccessDenied()

    @staticmethod
    def _ids(*values):
        return all(type(value) is uuid.UUID and value.int != 0
                   for value in values)
