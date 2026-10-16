"""Reconstruct same-project SOL-06 history from fixed payload and ref rows."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select

from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecHistoryView, StructuredSpecListPage,
    StructuredSpecSummaryView,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef,
)
from plm_assistant.modules.solution.application.structured_spec_payload import (
    StructuredSpecPayloadError, validate_structured_spec_payload,
)

from .orm import (
    StructuredSolutionSpecRow as Root,
    StructuredSpecArtifactRefRow as ArtifactRef,
    StructuredSpecEvidenceRefRow as EvidenceRef,
    StructuredSpecPayloadRow as Payload,
    StructuredSpecRequirementRefRow as RequirementRef,
    StructuredSpecSectionRefRow as SectionRef,
)
from .reference_deidentification_repository import _session


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ordered(rows: tuple[object, ...]) -> None:
    if tuple(row.ordinal for row in rows) != tuple(range(1, len(rows) + 1)):
        raise RuntimeError("StructuredSolutionSpec fixed collection is incomplete")


class SqlAlchemyStructuredSpecReadRepository:
    def list_versions(self, transaction: object, *, project_id: uuid.UUID,
                      before_spec_id: uuid.UUID | None,
                      limit: int) -> StructuredSpecListPage:
        if (not _id(project_id)
                or (before_spec_id is not None and not _id(before_spec_id))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError("invalid StructuredSolutionSpec list query")
        statement = select(Root, Payload).outerjoin(Payload, and_(
            Payload.structured_solution_spec_id
            == Root.structured_solution_spec_id,
            Payload.spec_series_id == Root.spec_series_id,
            Payload.project_id == Root.project_id,
            Payload.spec_type == Root.spec_type,
        )).where(Root.project_id == project_id)
        if before_spec_id is not None:
            statement = statement.where(
                Root.structured_solution_spec_id < before_spec_id)
        rows = tuple(_session(transaction).execute(statement.order_by(
            Root.structured_solution_spec_id.desc()).limit(limit + 1)
            .with_for_update(read=True, of=Root)).all())
        summaries = tuple(self._summary(root, payload, project_id)
                          for root, payload in rows)
        items = summaries[:limit]
        has_more = len(summaries) > limit
        return StructuredSpecListPage(
            items,
            items[-1].structured_solution_spec_id if has_more else None,
            has_more)

    def get(self, transaction: object, *, project_id: uuid.UUID,
            spec_id: uuid.UUID) -> StructuredSpecHistoryView | None:
        if not _id(project_id) or not _id(spec_id):
            return None
        session = _session(transaction)
        pair = session.execute(select(Root, Payload).join(
            Payload, Payload.structured_solution_spec_id
            == Root.structured_solution_spec_id,
        ).where(
            Root.structured_solution_spec_id == spec_id,
            Root.project_id == project_id,
            Payload.project_id == project_id,
            Payload.spec_series_id == Root.spec_series_id,
            Payload.spec_type == Root.spec_type,
        ).with_for_update(read=True, of=Root)).one_or_none()
        if pair is None:
            exists = session.execute(select(Root.structured_solution_spec_id).where(
                Root.structured_solution_spec_id == spec_id,
                Root.project_id == project_id,
            )).scalar_one_or_none()
            if exists is not None:
                raise RuntimeError("StructuredSolutionSpec payload is missing")
            return None
        root, payload = pair
        requirements = tuple(session.execute(select(RequirementRef).where(
            RequirementRef.structured_solution_spec_id == spec_id,
            RequirementRef.spec_series_id == root.spec_series_id,
            RequirementRef.project_id == project_id,
        ).order_by(RequirementRef.ordinal)).scalars())
        sections = tuple(session.execute(select(SectionRef).where(
            SectionRef.structured_solution_spec_id == spec_id,
            SectionRef.spec_series_id == root.spec_series_id,
            SectionRef.project_id == project_id,
        ).order_by(SectionRef.ordinal)).scalars())
        evidence = tuple(session.execute(select(EvidenceRef).where(
            EvidenceRef.structured_solution_spec_id == spec_id,
            EvidenceRef.spec_series_id == root.spec_series_id,
            EvidenceRef.project_id == project_id,
        ).order_by(EvidenceRef.ordinal)).scalars())
        artifacts = tuple(session.execute(select(ArtifactRef.output_artifact_id).where(
            ArtifactRef.structured_solution_spec_id == spec_id,
        )).scalars())
        for rows in (requirements, sections, evidence):
            _ordered(rows)
        if (not requirements or not sections or artifacts
                or payload.schema_version != 1
                or root.version_no < 1
                or root.version_state not in (
                    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                    "SUPERSEDED", "RESTRICTED")
                or (root.review_ref is None) != (root.review_round_ref is None)
                or (root.supersedes_version_ref is None) != (root.version_no == 1)
                or not _id(root.created_by)
                or len(root.content_fingerprint) != 32
                or len(payload.payload_fingerprint) != 32
                or len({row.requirement_id for row in requirements}) != len(requirements)
                or len({row.requirement_version_id for row in requirements}) != len(requirements)
                or len({row.solution_section_id for row in sections}) != len(sections)
                or len({row.solution_section_version_id for row in sections}) != len(sections)
                or len({row.evidence_id for row in evidence}) != len(evidence)):
            raise RuntimeError("StructuredSolutionSpec history is inconsistent")
        try:
            validated = validate_structured_spec_payload(
                root.spec_type, payload.payload_json)
        except StructuredSpecPayloadError:
            raise RuntimeError("StructuredSolutionSpec payload is invalid") from None
        if validated.payload_fingerprint != payload.payload_fingerprint:
            raise RuntimeError("StructuredSolutionSpec payload fingerprint changed")
        return StructuredSpecHistoryView(
            root.structured_solution_spec_id, root.spec_series_id,
            project_id, root.spec_type, root.version_no, root.version_state,
            bytes(root.content_fingerprint), validated.payload_json,
            bytes(payload.payload_fingerprint),
            tuple(SpecRequirementRef(row.requirement_id,
                                     row.requirement_version_id)
                  for row in requirements),
            tuple(SpecSectionRef(row.solution_section_id,
                                 row.solution_section_version_id)
                  for row in sections),
            tuple(row.evidence_id for row in evidence), artifacts,
            root.supersedes_version_ref, root.review_ref,
            root.review_round_ref, root.created_by, root.created_at,
        )

    @staticmethod
    def _summary(root: Root, payload: Payload | None,
                 project_id: uuid.UUID) -> StructuredSpecSummaryView:
        if (payload is None or root.project_id != project_id
                or payload.project_id != project_id
                or payload.spec_series_id != root.spec_series_id
                or payload.spec_type != root.spec_type
                or payload.schema_version != 1
                or root.version_no < 1
                or root.version_state not in (
                    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                    "SUPERSEDED", "RESTRICTED")
                or (root.supersedes_version_ref is None)
                != (root.version_no == 1)
                or (root.review_ref is None) != (root.review_round_ref is None)
                or not _id(root.created_by)
                or len(root.content_fingerprint) != 32
                or len(payload.payload_fingerprint) != 32):
            raise RuntimeError("StructuredSolutionSpec summary is inconsistent")
        return StructuredSpecSummaryView(
            root.structured_solution_spec_id, root.spec_series_id,
            project_id, root.spec_type, root.version_no, root.version_state,
            bytes(root.content_fingerprint), bytes(payload.payload_fingerprint),
            root.supersedes_version_ref, root.review_ref,
            root.review_round_ref, root.created_by, root.created_at)
