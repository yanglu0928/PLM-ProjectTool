"""Same-project SolutionSection identity and approved-pointer projection."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select

from plm_assistant.modules.solution.application.read_section import SectionCurrentView
from plm_assistant.modules.solution.application.read_section import SectionListPage, SectionSummaryView
from .orm import SolutionSectionRow as Root, SolutionSectionVersionRow as Version
from .reference_deidentification_repository import _session


class SqlAlchemySectionReadRepository:
    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     after_section_id: uuid.UUID | None,
                     limit: int) -> SectionListPage:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or (after_section_id is not None and (
                    type(after_section_id) is not uuid.UUID or after_section_id.int == 0))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError("invalid Section list query")
        statement = select(Root, Version).outerjoin(Version, and_(
            Version.solution_section_version_id == Root.current_approved_version_ref,
            Version.solution_section_id == Root.solution_section_id,
            Version.project_id == Root.project_id,
        )).where(Root.project_id == project_id)
        if after_section_id is not None:
            statement = statement.where(Root.solution_section_id > after_section_id)
        rows = tuple(_session(transaction).execute(statement.order_by(
            Root.solution_section_id).limit(limit + 1).with_for_update(
                read=True, of=Root)).all())
        items = []
        for root, version in rows[:limit]:
            self._require_approved_pointer(root, version, project_id)
            items.append(SectionSummaryView(
                solution_section_id=root.solution_section_id,
                solution_outline_id=root.solution_outline_id,
                project_id=project_id, section_key=root.section_key,
                section_state=root.section_state,
                current_approved_version_ref=root.current_approved_version_ref,
                created_at=root.created_at, etag=f'"v{root.lock_version}"',
            ))
        has_more = len(rows) > limit
        return SectionListPage(
            tuple(items), items[-1].solution_section_id if has_more else None,
            has_more)

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
        self._require_approved_pointer(root, version, project_id)
        return SectionCurrentView(
            solution_section_id=root.solution_section_id,
            solution_outline_id=root.solution_outline_id,
            project_id=root.project_id, section_key=root.section_key,
            section_state=root.section_state,
            current_approved_version_ref=root.current_approved_version_ref,
            created_by=root.created_by, created_at=root.created_at,
            etag=f'"v{root.lock_version}"',
        )

    @staticmethod
    def _require_approved_pointer(root: Root, version: Version | None,
                                  project_id: uuid.UUID) -> None:
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
