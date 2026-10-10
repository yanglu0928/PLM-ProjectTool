"""Fail-closed same-project reconstruction of fixed SectionVersion history."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef,
)

from .orm import (
    SolutionSectionEvidenceRefRow as EvidenceRef,
    SolutionSectionRequirementRefRow as RequirementRef,
    SolutionSectionVersionCreateResultRow as FirstResult,
    SolutionSectionVersionRow as Version,
)
from .reference_deidentification_repository import _session


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ordered(rows: tuple[object, ...], count: int) -> None:
    if (len(rows) != count
            or tuple(item.ordinal for item in rows) != tuple(range(1, count + 1))):
        raise RuntimeError("SectionVersion fixed collection is incomplete")


class SqlAlchemySectionVersionReadRepository:
    def list(self, transaction: object, *, project_id: uuid.UUID,
             section_id: uuid.UUID, before_version_no: int | None,
             limit: int) -> tuple[SectionVersionHistoryView, ...]:
        if (not _id(project_id) or not _id(section_id)
                or (before_version_no is not None and (
                    type(before_version_no) is not int or before_version_no < 2))
                or type(limit) is not int or not 1 <= limit <= 101):
            raise ValueError("invalid SectionVersion list query")
        statement = select(Version.solution_section_version_id).where(
            Version.project_id == project_id,
            Version.solution_section_id == section_id,
        )
        if before_version_no is not None:
            statement = statement.where(Version.version_no < before_version_no)
        ids = tuple(_session(transaction).execute(statement.order_by(
            Version.version_no.desc()).limit(limit)).scalars())
        items = []
        for version_id in ids:
            view = self.get(transaction, project_id=project_id,
                            section_id=section_id, version_id=version_id)
            if view is None:
                raise RuntimeError("SectionVersion list identity changed")
            items.append(view)
        if (len({item.version_no for item in items}) != len(items)
                or any(items[index - 1].version_no <= items[index].version_no
                       for index in range(1, len(items)))):
            raise RuntimeError("SectionVersion history order is inconsistent")
        return tuple(items)

    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionHistoryView | None:
        if not all(_id(item) for item in (project_id, section_id, version_id)):
            return None
        session = _session(transaction)
        pair = session.execute(select(Version, FirstResult).join(
            FirstResult,
            FirstResult.solution_section_version_id
            == Version.solution_section_version_id,
        ).where(
            Version.solution_section_version_id == version_id,
            Version.solution_section_id == section_id,
            Version.project_id == project_id,
            FirstResult.solution_section_id == section_id,
            FirstResult.project_id == project_id,
        ).with_for_update(read=True, of=Version)).one_or_none()
        if pair is None:
            exists = session.execute(select(Version.solution_section_version_id).where(
                Version.solution_section_version_id == version_id,
                Version.solution_section_id == section_id,
                Version.project_id == project_id,
            )).scalar_one_or_none()
            if exists is not None:
                raise RuntimeError("SectionVersion first result is missing")
            return None
        version, first = pair
        requirements = tuple(session.execute(select(RequirementRef).where(
            RequirementRef.solution_section_version_id == version_id,
            RequirementRef.solution_section_id == section_id,
            RequirementRef.project_id == project_id,
        ).order_by(RequirementRef.ordinal)).scalars())
        evidence = tuple(session.execute(select(EvidenceRef).where(
            EvidenceRef.solution_section_version_id == version_id,
            EvidenceRef.solution_section_id == section_id,
            EvidenceRef.project_id == project_id,
        ).order_by(EvidenceRef.ordinal)).scalars())
        _ordered(requirements, version.declared_requirement_count)
        _ordered(evidence, version.declared_evidence_count)
        if (version.version_no < 1
                or version.version_state not in (
                    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED")
                or len(version.content_fingerprint) != 32
                or not _id(version.created_by)
                or (version.review_ref is None) != (version.review_round_ref is None)
                or (version.content_document_version_ref is None)
                == (version.content_artifact_ref is None)
                or any(not _id(item.requirement_id)
                       or not _id(item.requirement_version_id)
                       for item in requirements)
                or any(not _id(item.evidence_id) for item in evidence)
                or len({item.requirement_id for item in requirements}) != len(requirements)
                or len({item.requirement_version_id for item in requirements}) != len(requirements)
                or len({item.evidence_id for item in evidence}) != len(evidence)
                or any(getattr(version, field) != getattr(first, field) for field in (
                    "solution_section_version_id", "solution_section_id", "project_id",
                    "version_no", "title", "content_document_version_ref",
                    "content_artifact_ref", "content_fingerprint", "assumptions",
                    "exclusions", "declared_requirement_count",
                    "declared_evidence_count", "supersedes_version_ref",
                    "created_by", "created_at"))):
            raise RuntimeError("SectionVersion historical projection is inconsistent")
        if (type(version.assumptions) is not list
                or type(version.exclusions) is not list
                or any(type(item) is not dict for item in (
                    *version.assumptions, *version.exclusions))):
            raise RuntimeError("SectionVersion declarations are inconsistent")
        return SectionVersionHistoryView(
            version.solution_section_version_id, section_id, project_id,
            version.version_no, version.version_state, version.title,
            version.content_document_version_ref, version.content_artifact_ref,
            bytes(version.content_fingerprint),
            tuple(SectionRequirementRef(item.requirement_id,
                                        item.requirement_version_id)
                  for item in requirements),
            tuple(item.evidence_id for item in evidence),
            tuple(dict(item) for item in version.assumptions),
            tuple(dict(item) for item in version.exclusions),
            version.supersedes_version_ref, version.review_ref,
            version.review_round_ref, version.created_by, version.created_at,
        )
