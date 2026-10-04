"""Review-owned recovery of the immutable first PROJECT submission response."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..application.project_persistence import (
    PersistedProjectReviewSubmission, SubmittedProjectReviewRef,
)
from ..application.read_snapshot import FixedReviewRoundSnapshot
from .orm import _tables
from .read_repository import SqlAlchemyReviewSnapshotReadRepository


class SqlAlchemyProjectReviewSubmissionRepository:
    def __init__(self) -> None:
        self._reader = SqlAlchemyReviewSnapshotReadRepository()

    @staticmethod
    def is_retryable_deadlock(error: Exception) -> bool:
        return (isinstance(error, DBAPIError)
                and getattr(error.orig, "sqlstate", None) == "40P01")

    @staticmethod
    def _session(tx: object) -> Session:
        session = getattr(tx, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Review submission transaction required")
        return session

    def get_project_submission(
        self, tx: object, *, project_id: uuid.UUID, round_id: uuid.UUID,
    ) -> PersistedProjectReviewSubmission | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(round_id) is not uuid.UUID or round_id.int == 0):
            return None
        session, rounds, roots = self._session(tx), _tables[1], _tables[0]
        row = session.execute(select(
            rounds.c.review_id, roots.c.created_by,
        ).join(
            roots, roots.c.review_id == rounds.c.review_id,
        ).where(
            rounds.c.review_round_id == round_id,
            rounds.c.scope == "PROJECT", rounds.c.project_id == project_id,
            roots.c.scope == "PROJECT", roots.c.project_id == project_id,
        ).with_for_update(read=True, of=(rounds, roots))).one_or_none()
        if row is None:
            return None
        fixed = self._reader.get_round(
            tx, "PROJECT", project_id, row.review_id, round_id,
        )
        if (type(fixed) is not FixedReviewRoundSnapshot
                or fixed.round_no != 1 or fixed.started_by != row.created_by):
            return None
        result = SubmittedProjectReviewRef(
            fixed.review.review_id, fixed.progress.round_id, project_id,
            fixed.review.subject_type, fixed.review.subject_id,
            fixed.subject_version_id, fixed.review.policy_code,
            fixed.progress.reviewer_ids, fixed.started_by,
            fixed.progress.started_at,
        )
        persisted = PersistedProjectReviewSubmission(fixed.review, result)
        persisted.__post_init__()
        return persisted
