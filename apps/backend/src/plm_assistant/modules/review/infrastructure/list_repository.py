"""Bounded REVIEW_LIST candidates inside the caller's active transaction."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..application.list_contract import (
    REVIEW_LIST_VIEWS,
    MyReviewAssignmentSummary,
    ReviewListActiveRoundSummary,
    ReviewListContractError,
    ReviewListItem,
    ReviewListPosition,
)
from .orm import _tables


def _uuid(value: object) -> bool:
    return type(value) is UUID and value.int != 0


def _utc(value: object) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None):
        raise ReviewListContractError()
    return value.astimezone(timezone.utc)


class SqlAlchemyReviewListRepository:
    def _session(
        self,
        transaction: object,
        *,
        project_id: UUID,
        actor_id: UUID,
        view: str,
        before: ReviewListPosition | None,
        limit: int,
    ) -> Session:
        session = getattr(transaction, "session", None)
        if (not isinstance(session, Session) or not session.in_transaction()
                or not _uuid(project_id) or not _uuid(actor_id)
                or type(view) is not str or view not in REVIEW_LIST_VIEWS
                or before is not None and type(before) is not ReviewListPosition
                or type(limit) is not int or not 1 <= limit <= 201):
            raise ValueError("active transaction and bounded Review list required")
        if before is not None:
            before.__post_init__()
        return session

    def list_candidates(
        self,
        transaction: object,
        *,
        project_id: UUID,
        actor_id: UUID,
        view: str,
        before: ReviewListPosition | None,
        limit: int,
    ) -> tuple[ReviewListItem, ...]:
        session = self._session(
            transaction,
            project_id=project_id,
            actor_id=actor_id,
            view=view,
            before=before,
            limit=limit,
        )
        reviews, rounds, assignments, decisions = _tables[:4]
        round_join = sa.and_(
            rounds.c.review_round_id == reviews.c.active_round_id,
            rounds.c.review_id == reviews.c.review_id,
            rounds.c.scope == reviews.c.scope,
            rounds.c.scope_project_key == reviews.c.scope_project_key,
        )
        assignment_join = sa.and_(
            assignments.c.review_round_id == rounds.c.review_round_id,
            assignments.c.review_id == reviews.c.review_id,
            assignments.c.scope == reviews.c.scope,
            assignments.c.scope_project_key == reviews.c.scope_project_key,
            assignments.c.reviewer_id == actor_id,
        )
        if view == "my_pending":
            source = reviews.join(rounds, round_join).join(
                assignments,
                sa.and_(assignment_join, assignments.c.assignment_state == "PENDING"),
            )
        else:
            source = reviews.outerjoin(rounds, round_join).outerjoin(
                assignments, assignment_join,
            )
        source = source.outerjoin(
            decisions,
            sa.and_(
                decisions.c.assignment_id == assignments.c.assignment_id,
                decisions.c.review_round_id == assignments.c.review_round_id,
                decisions.c.reviewer_id == assignments.c.reviewer_id,
                decisions.c.scope == assignments.c.scope,
                decisions.c.scope_project_key == assignments.c.scope_project_key,
            ),
        )
        query = sa.select(
            reviews.c.review_id,
            reviews.c.project_id,
            reviews.c.subject_type,
            reviews.c.subject_id,
            reviews.c.policy_code,
            reviews.c.review_state,
            reviews.c.created_by,
            reviews.c.created_at,
            reviews.c.lock_version,
            rounds.c.review_round_id,
            rounds.c.round_no,
            rounds.c.subject_version_id,
            rounds.c.started_at,
            assignments.c.assignment_id,
            assignments.c.assignment_state,
            decisions.c.decision,
            decisions.c.decided_at,
        ).select_from(source).where(
            reviews.c.scope == "PROJECT",
            reviews.c.scope_project_key == project_id,
            reviews.c.project_id == project_id,
        )
        if before is not None:
            query = query.where(sa.or_(
                reviews.c.created_at < before.created_at,
                sa.and_(
                    reviews.c.created_at == before.created_at,
                    reviews.c.review_id < before.review_id,
                ),
            ))
        query = query.order_by(
            reviews.c.created_at.desc(), reviews.c.review_id.desc(),
        ).limit(limit).with_for_update(read=True, of=reviews)
        items: list[ReviewListItem] = []
        for row in session.execute(query).mappings():
            assignment = None
            if row["assignment_id"] is not None:
                assignment = MyReviewAssignmentSummary(
                    row["assignment_id"],
                    row["assignment_state"],
                    row["decision"],
                    (_utc(row["decided_at"])
                     if row["decided_at"] is not None else None),
                )
            active_round = None
            if row["review_round_id"] is not None:
                active_round = ReviewListActiveRoundSummary(
                    row["review_round_id"],
                    row["round_no"],
                    row["subject_version_id"],
                    _utc(row["started_at"]),
                    assignment,
                )
            items.append(ReviewListItem(
                row["review_id"],
                row["project_id"],
                row["subject_type"],
                row["subject_id"],
                row["policy_code"],
                row["review_state"],
                row["created_by"],
                _utc(row["created_at"]),
                f'"v{row["lock_version"]}"',
                active_round,
            ))
        return tuple(items)
