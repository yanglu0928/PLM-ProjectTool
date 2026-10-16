"""PostgreSQL SurveyConclusion Review Subject persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update

from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.survey.application.conclusion_review_subject import (
    SurveyConclusionReviewLock,
)

from .conclusion_validation_repository import (
    SqlAlchemySurveyConclusionValidationRepository,
)
from .orm import SurveyConclusionRow, SurveyRow
from .survey_create_repository import _session


class SqlAlchemySurveyConclusionReviewRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemySurveyConclusionValidationRepository()

    def active_series_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        conclusion_series_id: uuid.UUID,
    ) -> bool:
        if not self._ids(project_id, conclusion_series_id):
            return False
        found = _session(transaction).execute(select(
            SurveyConclusionRow.conclusion_series_id,
        ).join(
            SurveyRow,
            (SurveyRow.survey_id == SurveyConclusionRow.survey_id)
            & (SurveyRow.project_id == SurveyConclusionRow.project_id),
        ).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_series_id == conclusion_series_id,
            SurveyRow.survey_state == "ACTIVE",
        ).limit(1).with_for_update(
            read=True, of=(SurveyConclusionRow, SurveyRow),
        )).scalar_one_or_none()
        return found == conclusion_series_id

    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        conclusion_series_id: uuid.UUID, survey_conclusion_id: uuid.UUID,
    ) -> SurveyConclusionReviewLock | None:
        if not self._ids(
                project_id, conclusion_series_id, survey_conclusion_id):
            return None
        session = _session(transaction)
        target = session.execute(select(SurveyConclusionRow).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_series_id == conclusion_series_id,
            SurveyConclusionRow.survey_conclusion_id == survey_conclusion_id,
        ).with_for_update(of=SurveyConclusionRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if target is None:
            return None
        survey = session.execute(select(SurveyRow).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == target.survey_id,
        ).with_for_update(of=SurveyRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        latest = session.execute(select(SurveyConclusionRow).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_series_id == conclusion_series_id,
        ).order_by(SurveyConclusionRow.version_no.desc()).limit(1).with_for_update(
            of=SurveyConclusionRow,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        approved = session.execute(select(
            SurveyConclusionRow.survey_conclusion_id,
        ).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_series_id == conclusion_series_id,
            SurveyConclusionRow.conclusion_state == "APPROVED",
        ).with_for_update(of=SurveyConclusionRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        snapshot = self._snapshots.lock_snapshot(
            transaction, project_id=project_id,
            survey_conclusion_id=survey_conclusion_id,
        )
        if survey is None or latest is None or snapshot is None:
            return None
        return SurveyConclusionReviewLock(
            snapshot, survey.survey_state, latest.survey_conclusion_id,
            approved, target.review_ref, target.review_round_ref,
        )

    def bind_start(
        self, transaction: object, *, before: SurveyConclusionReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID,
    ) -> None:
        if (type(before) is not SurveyConclusionReviewLock
                or not self._ids(review_id, round_id)):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        snapshot = before.snapshot
        changed = _session(transaction).execute(update(
            SurveyConclusionRow,
        ).where(
            SurveyConclusionRow.survey_conclusion_id
            == snapshot.survey_conclusion_id,
            SurveyConclusionRow.conclusion_series_id
            == snapshot.conclusion_series_id,
            SurveyConclusionRow.project_id == snapshot.project_id,
            SurveyConclusionRow.conclusion_state == "DRAFT",
            SurveyConclusionRow.review_ref.is_(None),
            SurveyConclusionRow.review_round_ref.is_(None),
        ).values(
            conclusion_state="IN_REVIEW", review_ref=review_id,
            review_round_ref=round_id,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()

    def consume_terminal(
        self, transaction: object, *, before: SurveyConclusionReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None:
        if (type(before) is not SurveyConclusionReviewLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        transition.__post_init__()
        snapshot = before.snapshot
        if (transition.before.subject_version_id
                != snapshot.survey_conclusion_id
                or transition.before.review.subject_id
                != snapshot.conclusion_series_id
                or before.review_ref != transition.before.review.review_id
                or before.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        previous = before.current_approved_version_ref
        if (version_state == "APPROVED" and previous is not None
                and previous != snapshot.survey_conclusion_id):
            changed = session.execute(update(SurveyConclusionRow).where(
                SurveyConclusionRow.survey_conclusion_id == previous,
                SurveyConclusionRow.conclusion_series_id
                == snapshot.conclusion_series_id,
                SurveyConclusionRow.project_id == snapshot.project_id,
                SurveyConclusionRow.conclusion_state == "APPROVED",
            ).values(conclusion_state="SUPERSEDED"))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        changed = session.execute(update(SurveyConclusionRow).where(
            SurveyConclusionRow.survey_conclusion_id
            == snapshot.survey_conclusion_id,
            SurveyConclusionRow.conclusion_series_id
            == snapshot.conclusion_series_id,
            SurveyConclusionRow.project_id == snapshot.project_id,
            SurveyConclusionRow.conclusion_state == "IN_REVIEW",
            SurveyConclusionRow.review_ref == before.review_ref,
            SurveyConclusionRow.review_round_ref == before.review_round_ref,
        ).values(conclusion_state=version_state))
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
        project_id = transition.before.review.project_id
        series_id = transition.before.review.subject_id
        version_id = transition.before.subject_version_id
        version = session.execute(select(SurveyConclusionRow).where(
            SurveyConclusionRow.survey_conclusion_id == version_id,
            SurveyConclusionRow.conclusion_series_id == series_id,
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_state == version_state,
            SurveyConclusionRow.review_ref == transition.before.review.review_id,
            SurveyConclusionRow.review_round_ref
            == transition.before.progress.round_id,
        ).with_for_update(of=SurveyConclusionRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        approved_count = session.execute(select(func.count()).select_from(
            SurveyConclusionRow,
        ).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_series_id == series_id,
            SurveyConclusionRow.conclusion_state == "APPROVED",
        )).scalar_one()
        if version is None:
            raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            valid = approved_count == 1
        else:
            valid = approved_count in (0, 1)
        if not valid:
            raise ReviewSubjectAccessDenied()

    @staticmethod
    def _ids(*values):
        return all(type(value) is uuid.UUID and value.int != 0
                   for value in values)
