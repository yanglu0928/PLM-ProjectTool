"""Same-transaction Section Review lock and lifecycle persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.solution.application.section_review_subject import (
    SectionReviewLock,
)

from .orm import (
    SectionReviewStateResultRow as Result,
    SolutionOutlineRow as Outline,
    SolutionSectionRow as Section,
    SolutionSectionVersionRow as Version,
)
from .outline_read_repository import SqlAlchemyOutlineReadRepository
from .reference_deidentification_repository import _session
from .section_read_repository import SqlAlchemySectionReadRepository
from .section_version_read_repository import SqlAlchemySectionVersionReadRepository


def _ids(*values: object) -> bool:
    return all(type(item) is uuid.UUID and item.int != 0 for item in values)


class SqlAlchemySectionReviewSubjectRepository:
    """Exclusive Outline→Section→Version lock blocks concurrent replacement."""

    def __init__(self) -> None:
        self._outlines = SqlAlchemyOutlineReadRepository()
        self._sections = SqlAlchemySectionReadRepository()
        self._versions = SqlAlchemySectionVersionReadRepository()

    def section_exists(self, transaction: object, *, project_id: uuid.UUID,
                       section_id: uuid.UUID) -> bool:
        if not _ids(project_id, section_id):
            return False
        found = _session(transaction).execute(select(
            Section.solution_section_id).where(
                Section.project_id == project_id,
                Section.solution_section_id == section_id,
            ).with_for_update(read=True)).scalar_one_or_none()
        return found == section_id

    def version_exists(self, transaction: object, *, project_id: uuid.UUID,
                       section_id: uuid.UUID,
                       version_id: uuid.UUID) -> bool:
        if not _ids(project_id, section_id, version_id):
            return False
        found = _session(transaction).execute(select(
            Version.solution_section_version_id).where(
                Version.project_id == project_id,
                Version.solution_section_id == section_id,
                Version.solution_section_version_id == version_id,
            ).with_for_update(read=True)).scalar_one_or_none()
        return found == version_id

    def lock_subject(self, transaction: object, *, project_id: uuid.UUID,
                     section_id: uuid.UUID,
                     version_id: uuid.UUID) -> SectionReviewLock | None:
        if not _ids(project_id, section_id, version_id):
            return None
        session = _session(transaction)
        outline_id = session.execute(select(Section.solution_outline_id).where(
            Section.project_id == project_id,
            Section.solution_section_id == section_id,
        )).scalar_one_or_none()
        if outline_id is None:
            return None
        outline = session.execute(select(Outline).where(
            Outline.project_id == project_id,
            Outline.solution_outline_id == outline_id,
        ).with_for_update().execution_options(
            populate_existing=True)).scalar_one_or_none()
        if outline is None or outline.outline_state != "ACTIVE":
            return None
        section = session.execute(select(Section).where(
            Section.project_id == project_id,
            Section.solution_section_id == section_id,
        ).with_for_update().execution_options(
            populate_existing=True)).scalar_one_or_none()
        if (section is None or section.solution_outline_id != outline_id
                or section.section_state != "ACTIVE"):
            return None
        if (self._outlines.get_current(
                transaction, project_id=project_id, outline_id=outline_id) is None
                or self._sections.get_current(
                    transaction, project_id=project_id,
                    section_id=section_id) is None):
            return None
        rows = tuple(session.execute(select(Version).where(
            Version.project_id == project_id,
            Version.solution_section_id == section_id,
        ).order_by(Version.version_no).with_for_update().execution_options(
            populate_existing=True)).scalars())
        if not rows:
            return None
        target = next((item for item in rows
                       if item.solution_section_version_id == version_id), None)
        approved = tuple(item for item in rows if item.version_state == "APPROVED")
        if (target is None or len(approved) > 1
                or section.current_approved_version_ref
                != (approved[0].solution_section_version_id if approved else None)):
            return None
        view = self._versions.get(
            transaction, project_id=project_id,
            section_id=section_id, version_id=version_id)
        if (view is None or view.version_no != target.version_no
                or view.version_state != target.version_state
                or view.review_ref != target.review_ref
                or view.review_round_ref != target.review_round_ref):
            return None
        return SectionReviewLock(
            view, rows[-1].solution_section_version_id,
            section.current_approved_version_ref)

    def bind_start(self, transaction: object, *, before: SectionReviewLock,
                   review_id: uuid.UUID, round_id: uuid.UUID,
                   actor_id: uuid.UUID) -> None:
        if (type(before) is not SectionReviewLock
                or not _ids(review_id, round_id, actor_id)):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        version = before.version
        if (version.version_state != "DRAFT"
                or before.latest_version_id
                != version.solution_section_version_id
                or version.review_ref is not None
                or version.review_round_ref is not None):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        changed = session.execute(update(Version).where(
            Version.solution_section_version_id
            == version.solution_section_version_id,
            Version.solution_section_id == version.solution_section_id,
            Version.project_id == version.project_id,
            Version.version_state == "DRAFT",
            Version.review_ref.is_(None),
            Version.review_round_ref.is_(None),
        ).values(version_state="IN_REVIEW", review_ref=review_id,
                 review_round_ref=round_id))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        session.add(Result(
            solution_section_version_id=version.solution_section_version_id,
            solution_section_id=version.solution_section_id,
            project_id=version.project_id, review_id=review_id,
            review_round_id=round_id, event_type="START",
            previous_approved_version_ref=before.current_approved_version_ref,
            current_approved_version_ref=before.current_approved_version_ref,
            actor_id=actor_id,
        ))
        try:
            session.flush()
        except Exception:
            raise ReviewSubjectAccessDenied() from None

    def consume_terminal(self, transaction: object, *, before: SectionReviewLock,
                         transition: ReviewSubjectTransition,
                         version_state: str) -> uuid.UUID:
        if (type(before) is not SectionReviewLock
                or type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        transition.__post_init__()
        version = before.version
        if (version.version_state != "IN_REVIEW"
                or before.latest_version_id
                != version.solution_section_version_id
                or transition.before.subject_version_id
                != version.solution_section_version_id
                or transition.before.review.project_id != version.project_id
                or transition.before.review.subject_id
                != version.solution_section_id
                or transition.before.subject_fingerprint
                != version.content_fingerprint
                or version.review_ref != transition.before.review.review_id
                or version.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        previous = before.current_approved_version_ref
        if version_state == "APPROVED" and previous is not None:
            changed = session.execute(update(Version).where(
                Version.solution_section_version_id == previous,
                Version.solution_section_id == version.solution_section_id,
                Version.project_id == version.project_id,
                Version.version_state == "APPROVED",
            ).values(version_state="SUPERSEDED"))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        changed = session.execute(update(Version).where(
            Version.solution_section_version_id
            == version.solution_section_version_id,
            Version.solution_section_id == version.solution_section_id,
            Version.project_id == version.project_id,
            Version.version_state == "IN_REVIEW",
            Version.review_ref == version.review_ref,
            Version.review_round_ref == version.review_round_ref,
        ).values(version_state=version_state))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        current = previous
        if version_state == "APPROVED":
            current = version.solution_section_version_id
            changed = session.execute(update(Section).where(
                Section.solution_section_id == version.solution_section_id,
                Section.project_id == version.project_id,
                Section.section_state == "ACTIVE",
                Section.current_approved_version_ref.is_not_distinct_from(
                    previous),
            ).values(current_approved_version_ref=current,
                     lock_version=Section.lock_version + 1))
            if changed.rowcount != 1:
                raise ReviewSubjectAccessDenied()
        result_id = uuid.UUID(new_uuid7())
        session.add(Result(
            review_state_result_id=result_id,
            solution_section_version_id=version.solution_section_version_id,
            solution_section_id=version.solution_section_id,
            project_id=version.project_id,
            review_id=version.review_ref,
            review_round_id=version.review_round_ref,
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

    def assert_terminal_consumed(self, transaction: object, *,
                                 transition: ReviewSubjectTransition,
                                 version_state: str) -> uuid.UUID:
        if (type(transition) is not ReviewSubjectTransition
                or version_state not in ("APPROVED", "RETURNED")):
            raise ReviewSubjectAccessDenied()
        transition.__post_init__()
        review = transition.before.review
        version_id = transition.before.subject_version_id
        locked = self.lock_subject(
            transaction, project_id=review.project_id,
            section_id=review.subject_id, version_id=version_id)
        if (type(locked) is not SectionReviewLock
                or locked.version.version_state != version_state
                or locked.version.content_fingerprint
                != transition.before.subject_fingerprint
                or locked.version.review_ref != review.review_id
                or locked.version.review_round_ref
                != transition.before.progress.round_id):
            raise ReviewSubjectAccessDenied()
        session = _session(transaction)
        result = session.execute(select(Result).where(
            Result.solution_section_version_id == version_id,
            Result.solution_section_id == review.subject_id,
            Result.project_id == review.project_id,
            Result.review_id == review.review_id,
            Result.review_round_id == transition.before.progress.round_id,
            Result.event_type == transition.after_progress.state.value,
            Result.actor_id == transition.actor_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True)).scalar_one_or_none()
        approved_count = session.execute(select(func.count()).select_from(
            Version).where(
                Version.solution_section_id == review.subject_id,
                Version.project_id == review.project_id,
                Version.version_state == "APPROVED",
        )).scalar_one()
        if result is None:
            raise ReviewSubjectAccessDenied()
        if version_state == "APPROVED":
            valid = (locked.current_approved_version_ref == version_id
                     and result.current_approved_version_ref == version_id
                     and result.previous_approved_version_ref != version_id
                     and approved_count == 1)
        else:
            valid = (locked.current_approved_version_ref
                     == result.previous_approved_version_ref
                     == result.current_approved_version_ref
                     and locked.current_approved_version_ref != version_id
                     and approved_count == (
                         0 if locked.current_approved_version_ref is None else 1))
        if not valid:
            raise ReviewSubjectAccessDenied()
        return result.review_state_result_id
