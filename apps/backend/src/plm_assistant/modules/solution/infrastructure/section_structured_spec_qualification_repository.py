"""Solution-owned same-project candidate reads; Review remains a separate port."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text

from .orm import StructuredSolutionSpecRow as SpecRow
from .reference_deidentification_repository import _session
from .section_version_read_repository import SqlAlchemySectionVersionReadRepository
from .structured_spec_read_repository import SqlAlchemyStructuredSpecReadRepository


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


_ANCESTOR = text("""
WITH RECURSIVE chain AS (
    SELECT solution_section_version_id, supersedes_version_ref, version_no
      FROM plm.sol_section_versions
     WHERE project_id=:project_id AND solution_section_id=:section_id
       AND solution_section_version_id=:latest_version_id
    UNION ALL
    SELECT parent.solution_section_version_id, parent.supersedes_version_ref,
           parent.version_no
      FROM plm.sol_section_versions parent
      JOIN chain child
        ON parent.solution_section_version_id=child.supersedes_version_ref
       AND parent.version_no=child.version_no-1
     WHERE parent.project_id=:project_id
       AND parent.solution_section_id=:section_id
)
SELECT EXISTS (SELECT 1 FROM chain WHERE solution_section_version_id=:ancestor_version_id)
""")


class SqlAlchemySectionSpecCandidateRepository:
    def __init__(self) -> None:
        self._specs = SqlAlchemyStructuredSpecReadRepository()

    def get(self, transaction: object, *, project_id: uuid.UUID,
            spec_id: uuid.UUID):
        return self._specs.get(transaction, project_id=project_id, spec_id=spec_id)

    def current_approved(self, transaction: object, *, project_id: uuid.UUID,
                         series_id: uuid.UUID) -> uuid.UUID | None:
        if not _id(project_id) or not _id(series_id):
            return None
        values = tuple(_session(transaction).execute(select(
            SpecRow.structured_solution_spec_id,
        ).where(
            SpecRow.project_id == project_id,
            SpecRow.spec_series_id == series_id,
            SpecRow.version_state == "APPROVED",
        ).with_for_update(read=True)).scalars())
        if len(values) > 1:
            raise RuntimeError("StructuredSpec current approval is ambiguous")
        return values[0] if values else None


class SqlAlchemySectionSpecSourceRepository:
    """Same-project SectionVersion history and explicit ancestor chain."""

    def __init__(self) -> None:
        self._sections = SqlAlchemySectionVersionReadRepository()

    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID, version_id: uuid.UUID):
        return self._sections.get(
            transaction, project_id=project_id,
            section_id=section_id, version_id=version_id)

    def is_ancestor(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID, latest_version_id: uuid.UUID,
                    ancestor_version_id: uuid.UUID) -> bool:
        if not all(_id(value) for value in (
                project_id, section_id, latest_version_id, ancestor_version_id)):
            return False
        return bool(_session(transaction).execute(_ANCESTOR, {
            "project_id": project_id,
            "section_id": section_id,
            "latest_version_id": latest_version_id,
            "ancestor_version_id": ancestor_version_id,
        }).scalar_one())
