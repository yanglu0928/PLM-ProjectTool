"""Lock parent Outline before Section and prove the next immutable version base."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select

from plm_assistant.modules.solution.application.section_version_base import (
    CurrentSectionVersionBase,
)

from .orm import (
    SolutionOutlineRow as Outline,
    SolutionOutlineVersionRow as OutlineVersion,
    SolutionSectionRow as Section,
    SolutionSectionVersionRow as SectionVersion,
)
from .outline_read_repository import SqlAlchemyOutlineReadRepository
from .reference_deidentification_repository import _session
from .section_read_repository import SqlAlchemySectionReadRepository


class SqlAlchemyCurrentSectionVersionBase:
    def current(self, transaction: object, *, project_id: uuid.UUID,
                section_id: uuid.UUID) -> CurrentSectionVersionBase | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(section_id) is not uuid.UUID or section_id.int == 0):
            return None
        session = _session(transaction)
        # Section's parent is immutable by Schema. This first read only selects
        # lock order; all identity fields are rechecked after both row locks.
        outline_id = session.execute(select(Section.solution_outline_id).where(
            Section.solution_section_id == section_id,
            Section.project_id == project_id,
        )).scalar_one_or_none()
        if outline_id is None:
            return None
        outline_row = session.execute(select(Outline, OutlineVersion).outerjoin(
            OutlineVersion, and_(
                OutlineVersion.solution_outline_version_id
                == Outline.current_approved_version_ref,
                OutlineVersion.solution_outline_id == Outline.solution_outline_id,
                OutlineVersion.project_id == Outline.project_id,
            ),
        ).where(
            Outline.solution_outline_id == outline_id,
            Outline.project_id == project_id,
        ).with_for_update(of=Outline)).one_or_none()
        if outline_row is None:
            return None
        outline, outline_approved = outline_row
        SqlAlchemyOutlineReadRepository._require_approved_pointer(
            outline, outline_approved, project_id)
        if (outline.outline_state != "ACTIVE"
                or type(outline.lock_version) is not int
                or outline.lock_version < 0):
            return None

        section_row = session.execute(select(Section, SectionVersion).outerjoin(
            SectionVersion, and_(
                SectionVersion.solution_section_version_id
                == Section.current_approved_version_ref,
                SectionVersion.solution_section_id == Section.solution_section_id,
                SectionVersion.project_id == Section.project_id,
            ),
        ).where(
            Section.solution_section_id == section_id,
            Section.project_id == project_id,
        ).with_for_update(of=Section)).one_or_none()
        if section_row is None:
            return None
        section, section_approved = section_row
        if (section.solution_outline_id != outline_id
                or section.section_state != "ACTIVE"
                or type(section.lock_version) is not int
                or section.lock_version < 0):
            return None
        SqlAlchemySectionReadRepository._require_approved_pointer(
            section, section_approved, project_id)

        latest = session.execute(select(SectionVersion).where(
            SectionVersion.solution_section_id == section_id,
            SectionVersion.project_id == project_id,
        ).order_by(SectionVersion.version_no.desc()).limit(1).with_for_update(
            read=True, of=SectionVersion)).scalar_one_or_none()
        if latest is None:
            return CurrentSectionVersionBase(
                project_id, outline_id, section_id, 1, None,
                outline.lock_version, section.lock_version)
        if (type(latest.version_no) is not int
                or not 1 <= latest.version_no < 2_147_483_647
                or type(latest.solution_section_version_id) is not uuid.UUID
                or latest.solution_section_version_id.int == 0):
            return None
        if latest.version_no == 1:
            if latest.supersedes_version_ref is not None:
                return None
        else:
            predecessor_id = latest.supersedes_version_ref
            if (type(predecessor_id) is not uuid.UUID
                    or predecessor_id.int == 0):
                return None
            predecessor_no = session.execute(select(SectionVersion.version_no).where(
                SectionVersion.solution_section_version_id == predecessor_id,
                SectionVersion.solution_section_id == section_id,
                SectionVersion.project_id == project_id,
            ).with_for_update(read=True, of=SectionVersion)).scalar_one_or_none()
            if predecessor_no != latest.version_no - 1:
                return None
        return CurrentSectionVersionBase(
            project_id, outline_id, section_id, latest.version_no + 1,
            latest.solution_section_version_id,
            outline.lock_version, section.lock_version)
