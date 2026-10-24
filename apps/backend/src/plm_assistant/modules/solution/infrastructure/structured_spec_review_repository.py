"""PostgreSQL SOL-06 Review Subject lock and lifecycle persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text, update

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.solution.application.structured_spec_review_subject import (
    StructuredSpecReviewLock,
)

from .orm import StructuredSolutionSpecRow, StructuredSpecReviewStateResultRow
from .reference_deidentification_repository import _session
from .structured_spec_validation_repository import (
    SqlAlchemyStructuredSpecValidationRepository,
)


class SqlAlchemyStructuredSpecReviewSubjectRepository:
    """Own the real series lock and the narrow Review state transitions."""

    def __init__(self) -> None:
        self._snapshots = SqlAlchemyStructuredSpecValidationRepository()

    def series_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        series_id: uuid.UUID,
    ) -> bool:
        if not _ids(project_id, series_id):
            return False
        found = _session(transaction).execute(select(
            StructuredSolutionSpecRow.spec_series_id,
        ).where(
            StructuredSolutionSpecRow.project_id == project_id,
            StructuredSolutionSpecRow.spec_series_id == series_id,
        ).limit(1).with_for_update(read=True)).scalar_one_or_none()
        return found == series_id

    def series_for_version(
        self, transaction: object, *, project_id: uuid.UUID,
        spec_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """Resolve immutable identity only; the Owner takes the real series lock."""
        if not _ids(project_id, spec_id):
            return None
        value = _session(transaction).execute(select(
            StructuredSolutionSpecRow.spec_series_id,
        ).where(
            StructuredSolutionSpecRow.project_id == project_id,
            StructuredSolutionSpecRow.structured_solution_spec_id == spec_id,
        )).scalar_one_or_none()
        return value if _ids(value) else None

    def version_exists(
        self, transaction: object, *, project_id: uuid.UUID,
        series_id: uuid.UUID, spec_id: uuid.UUID,
    ) -> bool:
        """Read-lock one immutable historical version without lifecycle locks."""
        if not _ids(project_id, series_id, spec_id):
            return False
        found = _session(transaction).execute(select(
            StructuredSolutionSpecRow.structured_solution_spec_id,
        ).where(
            StructuredSolutionSpecRow.project_id == project_id,
            StructuredSolutionSpecRow.spec_series_id == series_id,
            StructuredSolutionSpecRow.structured_solution_spec_id == spec_id,
        ).with_for_update(read=True)).scalar_one_or_none()
        return found == spec_id

    def lock_subject(
        self, transaction: object, *, project_id: uuid.UUID,
        series_id: uuid.UUID, spec_id: uuid.UUID,
    ) -> StructuredSpecReviewLock | None:
        if not _ids(project_id, series_id, spec_id):
            return None
        session = _session(transaction)
        session.execute(text(
            "SELECT pg_advisory_xact_lock(hashtextextended("
            "'plm.sol_structured_specs:' || CAST(:series_id AS text),0))"
        ), {"series_id": series_id})
        rows = tuple(session.execute(select(
            StructuredSolutionSpecRow,
        ).where(
            StructuredSolutionSpecRow.project_id == project_id,
            StructuredSolutionSpecRow.spec_series_id == series_id,
        ).order_by(
            StructuredSolutionSpecRow.version_no,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalars())
        if not rows:
            return None
        target = next((row for row in rows
                       if row.structured_solution_spec_id == spec_id), None)
        approved = tuple(row for row in rows
                         if row.version_state == "APPROVED")
        if target is None or len(approved) > 1:
            return None
        source = self._snapshots.lock_source(
            transaction, project_id=project_id, spec_id=spec_id)
        if (source is None
                or source.snapshot.spec_series_id != series_id
                or source.latest_version_ref
                != rows[-1].structured_solution_spec_id
                or source.latest_version_no != rows[-1].version_no):
            return None
        return StructuredSpecReviewLock(
            source.snapshot, rows[-1].structured_solution_spec_id,
            approved[0].structured_solution_spec_id if approved else None,
            target.review_ref, target.review_round_ref,
        )

    def bind_start(
        self, transaction: object, *, before: StructuredSpecReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> None:
        if (type(before) is not StructuredSpecReviewLock
                or not _ids(review_id, round_id, actor_id)):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        session, snapshot = _session(transaction), before.snapshot
        changed = session.execute(update(StructuredSolutionSpecRow).where(
            StructuredSolutionSpecRow.structured_solution_spec_id
            == snapshot.structured_solution_spec_id,
            StructuredSolutionSpecRow.spec_series_id
            == snapshot.spec_series_id,
            StructuredSolutionSpecRow.project_id == snapshot.project_id,
            StructuredSolutionSpecRow.version_state == "DRAFT",
            StructuredSolutionSpecRow.review_ref.is_(None),
            StructuredSolutionSpecRow.review_round_ref.is_(None),
        ).values(
            version_state="IN_REVIEW", review_ref=review_id,
            review_round_ref=round_id,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        session.add(StructuredSpecReviewStateResultRow(
            structured_solution_spec_id=snapshot.structured_solution_spec_id,
            spec_series_id=snapshot.spec_series_id,
            project_id=snapshot.project_id,
            review_id=review_id,
            review_round_id=round_id,
            event_type="START",
            previous_approved_version_ref=before.current_approved_version_ref,
            current_approved_version_ref=before.current_approved_version_ref,
            actor_id=actor_id,
        ))
        try:
            session.flush()
        except Exception:
            raise ReviewSubjectAccessDenied() from None

    def consume_terminal(
        self, transaction: object, *, before: StructuredSpecReviewLock,
        transition: ReviewSubjectTransition, version_state: str,
    ) -> uuid.UUID:
        if (type(before) is not StructuredSpecReviewLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in {"APPROVED", "RETURNED"}):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        transition.__post_init__()
        snapshot = before.snapshot
        if (transition.before.subject_version_id
                != snapshot.structured_solution_spec_id
                or transition.before.review.subject_id
                != snapshot.spec_series_id
                or before.review_ref != transition.before.review.review_id
                or before.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        previous = before.current_approved_version_ref
        if version_state == "APPROVED" and previous is not None:
            changed = session.execute(update(StructuredSolutionSpecRow).where(
                StructuredSolutionSpecRow.structured_solution_spec_id
                == previous,
                StructuredSolutionSpecRow.spec_series_id
                == snapshot.spec_series_id,
                StructuredSolutionSpecRow.project_id == snapshot.project_id,
                StructuredSolutionSpecRow.version_state == "APPROVED",
            ).values(version_state="SUPERSEDED"))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        changed = session.execute(update(StructuredSolutionSpecRow).where(
            StructuredSolutionSpecRow.structured_solution_spec_id
            == snapshot.structured_solution_spec_id,
            StructuredSolutionSpecRow.spec_series_id
            == snapshot.spec_series_id,
            StructuredSolutionSpecRow.project_id == snapshot.project_id,
            StructuredSolutionSpecRow.version_state == "IN_REVIEW",
            StructuredSolutionSpecRow.review_ref == before.review_ref,
            StructuredSolutionSpecRow.review_round_ref
            == before.review_round_ref,
        ).values(version_state=version_state))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        current = (snapshot.structured_solution_spec_id
                   if version_state == "APPROVED" else previous)
        result_id = uuid.UUID(new_uuid7())
        session.add(StructuredSpecReviewStateResultRow(
            review_state_result_id=result_id,
            structured_solution_spec_id=snapshot.structured_solution_spec_id,
            spec_series_id=snapshot.spec_series_id,
            project_id=snapshot.project_id,
            review_id=transition.before.review.review_id,
            review_round_id=transition.before.progress.round_id,
            event_type=transition.after_progress.state.value,
            previous_approved_version_ref=previous,
            current_approved_version_ref=current,
            actor_id=transition.actor_id,
        ))
        try:
            session.flush()
        except Exception:
            raise ReviewSubjectAccessDenied() from None
        return result_id

    def assert_terminal_consumed(
        self, transaction: object, *, transition: ReviewSubjectTransition,
        version_state: str,
    ) -> uuid.UUID:
        if (type(transition) is not ReviewSubjectTransition
                or version_state not in {"APPROVED", "RETURNED"}):
            raise ReviewSubjectAccessDenied()
        transition.__post_init__()
        review = transition.before.review
        version_id = transition.before.subject_version_id
        locked = self.lock_subject(
            transaction, project_id=review.project_id,
            series_id=review.subject_id, spec_id=version_id)
        if (type(locked) is not StructuredSpecReviewLock
                or locked.snapshot.version_state != version_state
                or locked.review_ref != review.review_id
                or locked.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        result = session.execute(select(
            StructuredSpecReviewStateResultRow,
        ).where(
            StructuredSpecReviewStateResultRow.structured_solution_spec_id
            == version_id,
            StructuredSpecReviewStateResultRow.spec_series_id
            == review.subject_id,
            StructuredSpecReviewStateResultRow.project_id
            == review.project_id,
            StructuredSpecReviewStateResultRow.review_id == review.review_id,
            StructuredSpecReviewStateResultRow.review_round_id
            == transition.before.progress.round_id,
            StructuredSpecReviewStateResultRow.event_type
            == transition.after_progress.state.value,
            StructuredSpecReviewStateResultRow.actor_id
            == transition.actor_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        approved_count = session.execute(select(func.count()).select_from(
            StructuredSolutionSpecRow,
        ).where(
            StructuredSolutionSpecRow.spec_series_id == review.subject_id,
            StructuredSolutionSpecRow.project_id == review.project_id,
            StructuredSolutionSpecRow.version_state == "APPROVED",
        )).scalar_one()
        if result is None:
            raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            valid = (
                locked.current_approved_version_ref == version_id
                and result.current_approved_version_ref == version_id
                and result.previous_approved_version_ref != version_id
                and approved_count == 1
            )
        else:
            valid = (
                locked.current_approved_version_ref
                == result.previous_approved_version_ref
                == result.current_approved_version_ref
                and locked.current_approved_version_ref != version_id
                and approved_count == (
                    0 if locked.current_approved_version_ref is None else 1)
            )
        if not valid:
            raise ReviewSubjectAccessDenied()
        return result.review_state_result_id


def _ids(*values: object) -> bool:
    return all(type(value) is uuid.UUID and value.int != 0 for value in values)
