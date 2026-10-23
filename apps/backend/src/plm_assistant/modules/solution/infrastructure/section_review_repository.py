"""Same-transaction Section Review lock and START persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update

from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
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
