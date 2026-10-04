"""PostgreSQL Handover Review Subject lock and formalization persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text, update

from plm_assistant.modules.handover.application.review_subject import (
    HandoverReviewLock,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)

from .analysis_create_repository import _session
from .orm import (
    HandoverActionItemRow, HandoverAnalysisItemRow, HandoverAnalysisRow,
    HandoverAnalysisVersionRow,
)
from .version_validation_repository import (
    SqlAlchemyHandoverVersionValidationRepository,
)


class SqlAlchemyHandoverReviewSubjectRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemyHandoverVersionValidationRepository()

    def active_analysis_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_id: uuid.UUID,
    ) -> bool:
        if not self._ids(project_id, analysis_id):
            return False
        found = _session(transaction).execute(select(
            HandoverAnalysisRow.handover_analysis_id,
        ).where(
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.handover_analysis_id == analysis_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
        ).with_for_update(read=True)).scalar_one_or_none()
        return found == analysis_id

    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_id: uuid.UUID, analysis_version_id: uuid.UUID,
    ) -> HandoverReviewLock | None:
        if not self._ids(project_id, analysis_id, analysis_version_id):
            return None
        session = _session(transaction)
        analysis = session.execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.handover_analysis_id == analysis_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.handover_analysis_id == analysis_id,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == analysis_version_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if analysis is None or version is None:
            return None
        snapshot = self._snapshots.lock_snapshot(
            transaction, project_id=project_id,
            handover_analysis_id=analysis_id,
            handover_analysis_version_id=analysis_version_id,
        )
        latest = session.execute(select(
            HandoverAnalysisVersionRow.handover_analysis_version_id,
        ).where(
            HandoverAnalysisVersionRow.handover_analysis_id == analysis_id,
            HandoverAnalysisVersionRow.project_id == project_id,
        ).order_by(HandoverAnalysisVersionRow.version_no.desc()).limit(1)
        ).scalar_one_or_none()
        items = tuple(session.execute(select(
            HandoverAnalysisItemRow.analysis_item_id,
            HandoverAnalysisItemRow.item_state,
        ).where(
            HandoverAnalysisItemRow.handover_analysis_version_id
            == analysis_version_id,
        ).order_by(HandoverAnalysisItemRow.ordinal).with_for_update(read=True)
        ).all())
        covered = frozenset(session.execute(select(
            HandoverActionItemRow.source_item_id,
        ).where(
            HandoverActionItemRow.project_id == project_id,
            HandoverActionItemRow.source_kind == "ANALYSIS_ITEM",
            HandoverActionItemRow.source_analysis_version_ref
            == analysis_version_id,
            HandoverActionItemRow.action_state != "CANCELLED",
        ).with_for_update(read=True)).scalars())
        if snapshot is None or latest is None:
            return None
        return HandoverReviewLock(
            snapshot, analysis.analysis_state, analysis.lock_version,
            analysis.current_approved_version_ref, latest,
            version.review_ref, version.review_round_ref, items, covered,
        )

    def bind_start(
        self, transaction: object, *, before: HandoverReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None:
        if (type(before) is not HandoverReviewLock
                or not self._ids(review_id, round_id, actor_id)):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        session, snapshot = _session(transaction), before.snapshot
        changed = session.execute(update(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == snapshot.handover_analysis_version_id,
            HandoverAnalysisVersionRow.handover_analysis_id
            == snapshot.handover_analysis_id,
            HandoverAnalysisVersionRow.project_id == snapshot.project_id,
            HandoverAnalysisVersionRow.version_state == "DRAFT",
            HandoverAnalysisVersionRow.review_ref.is_(None),
            HandoverAnalysisVersionRow.review_round_ref.is_(None),
        ).values(
            version_state="IN_REVIEW", review_ref=review_id,
            review_round_ref=round_id,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        changed = session.execute(update(HandoverAnalysisRow).where(
            HandoverAnalysisRow.handover_analysis_id
            == snapshot.handover_analysis_id,
            HandoverAnalysisRow.project_id == snapshot.project_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
            HandoverAnalysisRow.lock_version == before.analysis_lock_version,
        ).values(
            updated_by=actor_id, updated_at=text("statement_timestamp()"),
            lock_version=HandoverAnalysisRow.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()

    def consume_terminal(
        self, transaction: object, *, before: HandoverReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> None:
        if (type(before) is not HandoverReviewLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        transition.__post_init__()
        snapshot = before.snapshot
        if (transition.before.subject_version_id
                != snapshot.handover_analysis_version_id
                or transition.before.review.subject_id
                != snapshot.handover_analysis_id
                or before.review_ref != transition.before.review.review_id
                or before.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        previous = before.current_approved_version_ref
        if version_state == "APPROVED" and previous is not None:
            changed = session.execute(update(HandoverAnalysisVersionRow).where(
                HandoverAnalysisVersionRow.handover_analysis_version_id
                == previous,
                HandoverAnalysisVersionRow.handover_analysis_id
                == snapshot.handover_analysis_id,
                HandoverAnalysisVersionRow.project_id == snapshot.project_id,
                HandoverAnalysisVersionRow.version_state == "APPROVED",
            ).values(version_state="SUPERSEDED"))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            changed = session.execute(update(HandoverAnalysisItemRow).where(
                HandoverAnalysisItemRow.handover_analysis_version_id
                == snapshot.handover_analysis_version_id,
                HandoverAnalysisItemRow.item_state == "CANDIDATE",
            ).values(item_state="CONFIRMED"))
            if changed.rowcount != len(before.item_states):
                raise ReviewSubjectAccessDenied()
        changed = session.execute(update(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == snapshot.handover_analysis_version_id,
            HandoverAnalysisVersionRow.handover_analysis_id
            == snapshot.handover_analysis_id,
            HandoverAnalysisVersionRow.project_id == snapshot.project_id,
            HandoverAnalysisVersionRow.version_state == "IN_REVIEW",
            HandoverAnalysisVersionRow.review_ref == before.review_ref,
            HandoverAnalysisVersionRow.review_round_ref
            == before.review_round_ref,
        ).values(version_state=version_state))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        values = {
            "updated_by": transition.actor_id,
            "updated_at": text("statement_timestamp()"),
            "lock_version": HandoverAnalysisRow.lock_version + 1,
        }
        if version_state == "APPROVED":
            values["current_approved_version_ref"] = (
                snapshot.handover_analysis_version_id
            )
        changed = session.execute(update(HandoverAnalysisRow).where(
            HandoverAnalysisRow.handover_analysis_id
            == snapshot.handover_analysis_id,
            HandoverAnalysisRow.project_id == snapshot.project_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
            HandoverAnalysisRow.lock_version == before.analysis_lock_version,
            HandoverAnalysisRow.current_approved_version_ref.is_(None)
            if previous is None else
            HandoverAnalysisRow.current_approved_version_ref == previous,
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
        analysis_id = transition.before.review.subject_id
        project_id = transition.before.review.project_id
        version_id = transition.before.subject_version_id
        analysis = session.execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.handover_analysis_id == analysis_id,
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        version = session.execute(select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == version_id,
            HandoverAnalysisVersionRow.handover_analysis_id == analysis_id,
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.version_state == version_state,
            HandoverAnalysisVersionRow.review_ref
            == transition.before.review.review_id,
            HandoverAnalysisVersionRow.review_round_ref
            == transition.before.progress.round_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        approved_count = session.execute(select(func.count()).select_from(
            HandoverAnalysisVersionRow,
        ).where(
            HandoverAnalysisVersionRow.handover_analysis_id == analysis_id,
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.version_state == "APPROVED",
        )).scalar_one()
        confirmed_count = session.execute(select(func.count()).select_from(
            HandoverAnalysisItemRow,
        ).where(
            HandoverAnalysisItemRow.handover_analysis_version_id == version_id,
            HandoverAnalysisItemRow.item_state == "CONFIRMED",
        )).scalar_one()
        item_count = session.execute(select(func.count()).select_from(
            HandoverAnalysisItemRow,
        ).where(
            HandoverAnalysisItemRow.handover_analysis_version_id == version_id,
        )).scalar_one()
        if analysis is None or version is None:
            raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            valid = (analysis.current_approved_version_ref == version_id
                     and approved_count == 1
                     and confirmed_count == item_count)
        else:
            valid = (analysis.current_approved_version_ref != version_id
                     and approved_count == (
                         0 if analysis.current_approved_version_ref is None
                         else 1)
                     and confirmed_count == 0)
        if not valid:
            raise ReviewSubjectAccessDenied()

    @staticmethod
    def _ids(*values):
        return all(type(value) is uuid.UUID and value.int != 0
                   for value in values)
