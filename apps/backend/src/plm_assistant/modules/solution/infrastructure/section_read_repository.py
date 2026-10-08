"""Same-project SolutionSection identity and approved-pointer projection."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select

from plm_assistant.modules.solution.application.read_section import SectionCurrentView
from .orm import SolutionSectionRow as Root, SolutionSectionVersionRow as Version
from .reference_deidentification_repository import _session


class SqlAlchemySectionReadRepository:
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID) -> SectionCurrentView | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(section_id) is not uuid.UUID or section_id.int == 0):
            return None
        row = _session(transaction).execute(select(Root, Version).outerjoin(
            Version, and_(
                Version.solution_section_version_id == Root.current_approved_version_ref,
                Version.solution_section_id == Root.solution_section_id,
                Version.project_id == Root.project_id,
            ),
        ).where(
            Root.solution_section_id == section_id, Root.project_id == project_id,
        ).with_for_update(read=True, of=Root)).one_or_none()
        if row is None:
            return None
        root, version = row
        if ((root.current_approved_version_ref is None and version is not None)
                or (root.current_approved_version_ref is not None and (
                    version is None
                    or version.solution_section_version_id
                    != root.current_approved_version_ref
                    or version.solution_section_id != root.solution_section_id
                    or version.project_id != project_id
                    or version.version_state != "APPROVED"
                    or version.review_ref is None
                    or version.review_round_ref is None))):
            raise RuntimeError("Section approved pointer is inconsistent")
        return SectionCurrentView(
            solution_section_id=root.solution_section_id,
            solution_outline_id=root.solution_outline_id,
            project_id=root.project_id, section_key=root.section_key,
            section_state=root.section_state,
            current_approved_version_ref=root.current_approved_version_ref,
            created_by=root.created_by, created_at=root.created_at,
            etag=f'"v{root.lock_version}"',
        )
