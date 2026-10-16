"""Fail-closed reconstruction of immutable OutlineVersion fixed history."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef, OutlineRequirementRef,
)

from .orm import (
    SolutionOutlineRequirementRefRow as RequirementRef,
    SolutionOutlineReferenceRefRow as ReferenceRef,
    SolutionOutlineSectionRow as SectionRef,
    SolutionOutlineVersionCreateResultRow as FirstResult,
    SolutionOutlineVersionRow as Version,
)
from .reference_deidentification_repository import _session


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ordered(rows: tuple[object, ...], count: int) -> None:
    if (len(rows) != count
            or tuple(item.ordinal for item in rows) != tuple(range(1, count + 1))):
        raise RuntimeError("OutlineVersion fixed collection is incomplete")


class SqlAlchemyOutlineVersionReadRepository:
    def list(self, transaction: object, *, project_id: uuid.UUID,
             outline_id: uuid.UUID, before_version_no: int | None,
             limit: int) -> tuple[OutlineVersionHistoryView, ...]:
        if (not _id(project_id) or not _id(outline_id)
                or (before_version_no is not None and (
                    type(before_version_no) is not int or before_version_no < 2))
                or type(limit) is not int or not 1 <= limit <= 101):
            raise ValueError("invalid OutlineVersion list query")
        statement = select(Version.solution_outline_version_id).where(
            Version.project_id == project_id,
            Version.solution_outline_id == outline_id,
        )
        if before_version_no is not None:
            statement = statement.where(Version.version_no < before_version_no)
        ids = tuple(_session(transaction).execute(statement.order_by(
            Version.version_no.desc()).limit(limit)).scalars())
        items = []
        for version_id in ids:
            view = self.get(transaction, project_id=project_id,
                            outline_id=outline_id, version_id=version_id)
            if view is None:
                raise RuntimeError("OutlineVersion list identity changed")
            items.append(view)
        if (len({item.version_no for item in items}) != len(items)
                or any(items[index - 1].version_no <= items[index].version_no
                       for index in range(1, len(items)))):
            raise RuntimeError("OutlineVersion history order is inconsistent")
        return tuple(items)

    def get(self, transaction: object, *, project_id: uuid.UUID,
            outline_id: uuid.UUID,
            version_id: uuid.UUID) -> OutlineVersionHistoryView | None:
        if not all(_id(item) for item in (project_id, outline_id, version_id)):
            return None
        session = _session(transaction)
        pair = session.execute(select(Version, FirstResult).join(
            FirstResult,
            FirstResult.solution_outline_version_id
            == Version.solution_outline_version_id,
        ).where(
            Version.solution_outline_version_id == version_id,
            Version.solution_outline_id == outline_id,
            Version.project_id == project_id,
            FirstResult.solution_outline_id == outline_id,
            FirstResult.project_id == project_id,
        ).with_for_update(read=True, of=Version)).one_or_none()
        if pair is None:
            # Distinguish a missing version from a corrupt missing first result.
            exists = session.execute(select(Version.solution_outline_version_id).where(
                Version.solution_outline_version_id == version_id,
                Version.solution_outline_id == outline_id,
                Version.project_id == project_id,
            )).scalar_one_or_none()
            if exists is not None:
                raise RuntimeError("OutlineVersion first result is missing")
            return None
        version, first = pair
        sections = tuple(session.execute(select(SectionRef).where(
            SectionRef.solution_outline_version_id == version_id,
            SectionRef.solution_outline_id == outline_id,
            SectionRef.project_id == project_id,
        ).order_by(SectionRef.ordinal)).scalars())
        requirements = tuple(session.execute(select(RequirementRef).where(
            RequirementRef.solution_outline_version_id == version_id,
            RequirementRef.solution_outline_id == outline_id,
            RequirementRef.project_id == project_id,
        ).order_by(RequirementRef.ordinal)).scalars())
        references = tuple(session.execute(select(ReferenceRef).where(
            ReferenceRef.solution_outline_version_id == version_id,
            ReferenceRef.solution_outline_id == outline_id,
            ReferenceRef.project_id == project_id,
        ).order_by(ReferenceRef.ordinal)).scalars())
        _ordered(sections, version.declared_section_count)
        _ordered(requirements, version.declared_requirement_count)
        _ordered(references, version.declared_reference_count)
        if (version.version_no < 1
                or version.version_state not in (
                    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED")
                or len(version.content_fingerprint) != 32
                or not _id(version.created_by)
                or (version.review_ref is None) != (version.review_round_ref is None)
                or any(not _id(item.solution_section_id) for item in sections)
                or any(not _id(item.requirement_id)
                       or not _id(item.requirement_version_id)
                       for item in requirements)
                or any(item.reference_scope not in ("PROJECT", "GLOBAL")
                       or not _id(item.reference_solution_id)
                       or not _id(item.reference_version_id)
                       or (item.source_project_id != project_id
                           if item.reference_scope == "PROJECT"
                           else item.source_project_id is not None)
                       for item in references)
                or len({item.solution_section_id for item in sections}) != len(sections)
                or len({item.requirement_id for item in requirements}) != len(requirements)
                or len({item.reference_solution_id for item in references}) != len(references)
                or any(getattr(version, field) != getattr(first, field) for field in (
                    "solution_outline_version_id", "solution_outline_id", "project_id",
                    "version_no", "content_fingerprint", "missing_declarations",
                    "conflict_declarations", "declared_section_count",
                    "declared_requirement_count", "declared_reference_count",
                    "supersedes_version_ref", "created_by", "created_at"))):
            raise RuntimeError("OutlineVersion historical projection is inconsistent")
        if (type(version.missing_declarations) is not list
                or type(version.conflict_declarations) is not list
                or any(type(item) is not dict for item in (
                    *version.missing_declarations, *version.conflict_declarations))):
            raise RuntimeError("OutlineVersion declarations are inconsistent")
        return OutlineVersionHistoryView(
            version.solution_outline_version_id, outline_id, project_id,
            version.version_no, version.version_state,
            bytes(version.content_fingerprint),
            tuple(item.solution_section_id for item in sections),
            tuple(OutlineRequirementRef(item.requirement_id,
                                        item.requirement_version_id)
                  for item in requirements),
            tuple(OutlineReferenceRef(item.reference_scope,
                                      item.reference_solution_id,
                                      item.reference_version_id)
                  for item in references),
            tuple(dict(item) for item in version.missing_declarations),
            tuple(dict(item) for item in version.conflict_declarations),
            version.supersedes_version_ref, version.review_ref,
            version.review_round_ref, version.created_by, version.created_at,
        )
