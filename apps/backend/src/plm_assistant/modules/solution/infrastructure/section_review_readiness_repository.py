"""Same-transaction shared locks for the latest Section Review candidate."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from .orm import (
    SolutionOutlineRow as Outline,
    SolutionSectionRow as Section,
    SolutionSectionVersionRow as Version,
)
from .reference_deidentification_repository import _session
from .outline_read_repository import SqlAlchemyOutlineReadRepository
from .section_read_repository import SqlAlchemySectionReadRepository
from .section_version_read_repository import SqlAlchemySectionVersionReadRepository


class SqlAlchemySectionReviewReadinessRepository:
    def __init__(self) -> None:
        self._versions = SqlAlchemySectionVersionReadRepository()

    def lock_latest(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID, version_id: uuid.UUID):
        if (transaction is None or any(type(value) is not uuid.UUID or value.int == 0
                                       for value in (project_id, section_id, version_id))):
            return None
        session = _session(transaction)
        # Same parent-before-child order as SectionVersion CREATE. Its exclusive
        # parent locks prevent a new version/archival during this observation.
        outline_id = session.execute(select(Section.solution_outline_id).where(
            Section.solution_section_id == section_id,
            Section.project_id == project_id)).scalar_one_or_none()
        if outline_id is None:
            return None
        outline = session.execute(select(Outline).where(
            Outline.solution_outline_id == outline_id,
            Outline.project_id == project_id).with_for_update(
                read=True, of=Outline)).scalar_one_or_none()
        if outline is None or outline.outline_state != "ACTIVE":
            return None
        section = session.execute(select(Section).where(
            Section.solution_section_id == section_id,
            Section.project_id == project_id).with_for_update(
                read=True, of=Section)).scalar_one_or_none()
        if (section is None or section.solution_outline_id != outline_id
                or section.section_state != "ACTIVE"):
            return None
        # Fail closed on a broken approved pointer even when the candidate is
        # still DRAFT; the later terminal transition will depend on this root.
        if (SqlAlchemyOutlineReadRepository().get_current(
                transaction, project_id=project_id, outline_id=outline_id) is None
                or SqlAlchemySectionReadRepository().get_current(
                    transaction, project_id=project_id, section_id=section_id) is None):
            return None
        latest = session.execute(select(Version).where(
            Version.solution_section_id == section_id,
            Version.project_id == project_id).order_by(
                Version.version_no.desc()).limit(1).with_for_update(
                    read=True, of=Version)).scalar_one_or_none()
        if (latest is None or latest.solution_section_version_id != version_id
                or latest.version_state != "DRAFT"):
            return None
        return self._versions.get(transaction, project_id=project_id,
                                  section_id=section_id, version_id=version_id)
