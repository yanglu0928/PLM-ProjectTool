"""Shared-locked reconstruction of one fixed SOL-06 validation source."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select, text

from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
    StructuredSpecInputError, validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    StructuredSpecValidationSnapshot,
)
from plm_assistant.modules.solution.application.structured_spec_validation_source import (
    StructuredSpecValidationSource,
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


_STATES = frozenset((
    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
    "SUPERSEDED", "RESTRICTED",
))


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ordered(rows: tuple[object, ...]) -> None:
    if tuple(row.ordinal for row in rows) != tuple(range(1, len(rows) + 1)):
        raise RuntimeError("StructuredSolutionSpec fixed collection is incomplete")


def _bound(rows: tuple[object, ...], *, spec_id: uuid.UUID,
           series_id: uuid.UUID, project_id: uuid.UUID) -> None:
    if any((row.structured_solution_spec_id, row.spec_series_id,
            row.project_id) != (spec_id, series_id, project_id)
           for row in rows):
        raise RuntimeError("StructuredSolutionSpec fixed collection changed")


class SqlAlchemyStructuredSpecValidationRepository:
    def lock_source(
        self, transaction: object, *, project_id: uuid.UUID,
        spec_id: uuid.UUID,
    ) -> StructuredSpecValidationSource | None:
        if not _id(project_id) or not _id(spec_id):
            return None
        session = _session(transaction)
        identity = session.execute(select(Root.spec_series_id).where(
            Root.structured_solution_spec_id == spec_id,
            Root.project_id == project_id,
        )).one_or_none()
        if identity is None:
            return None
        series_id = identity.spec_series_id
        if not _id(series_id):
            raise RuntimeError("StructuredSolutionSpec validation identity is invalid")

        # CREATE/REVISE use the matching exclusive transaction lock. Shared
        # validation observations can run together but cannot straddle a revision.
        session.execute(text(
            "SELECT pg_advisory_xact_lock_shared(hashtextextended("
            "'plm.sol_structured_specs:' || CAST(:series_id AS text),0))"),
            {"series_id": series_id})
        pair = session.execute(select(Root, Payload).join(Payload, and_(
            Payload.structured_solution_spec_id
            == Root.structured_solution_spec_id,
            Payload.spec_series_id == Root.spec_series_id,
            Payload.project_id == Root.project_id,
            Payload.spec_type == Root.spec_type,
        )).where(
            Root.structured_solution_spec_id == spec_id,
            Root.spec_series_id == series_id,
            Root.project_id == project_id,
        ).with_for_update(read=True, of=Root).execution_options(
            populate_existing=True,
        )).one_or_none()
        latest = session.execute(select(Root).where(
            Root.spec_series_id == series_id,
            Root.project_id == project_id,
        ).order_by(Root.version_no.desc()).limit(1).with_for_update(
            read=True, of=Root,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if pair is None or latest is None:
            raise RuntimeError("StructuredSolutionSpec validation root is incomplete")
        root, payload = pair

        requirements = self._rows(
            session, RequirementRef, spec_id, series_id, project_id)
        sections = self._rows(
            session, SectionRef, spec_id, series_id, project_id)
        evidence = self._rows(
            session, EvidenceRef, spec_id, series_id, project_id)
        artifacts = self._rows(
            session, ArtifactRef, spec_id, series_id, project_id)
        for rows in (requirements, sections, evidence, artifacts):
            _ordered(rows)
            _bound(rows, spec_id=spec_id, series_id=series_id,
                   project_id=project_id)

        if (root.structured_solution_spec_id != spec_id
                or root.spec_series_id != series_id
                or root.project_id != project_id
                or payload.structured_solution_spec_id != spec_id
                or payload.spec_series_id != series_id
                or payload.project_id != project_id
                or payload.spec_type != root.spec_type
                or payload.schema_version != 1
                or root.version_state not in _STATES
                or (root.supersedes_version_ref is None)
                != (root.version_no == 1)
                or (root.review_ref is None) != (root.review_round_ref is None)
                or not _id(root.created_by)
                or latest.structured_solution_spec_id is None
                or latest.spec_series_id != series_id
                or latest.project_id != project_id
                or latest.spec_type != root.spec_type
                or latest.version_state not in _STATES
                or (latest.supersedes_version_ref is None)
                != (latest.version_no == 1)
                or (latest.review_ref is None)
                != (latest.review_round_ref is None)
                or not _id(latest.structured_solution_spec_id)
                or not _id(latest.created_by)
                or latest.version_no < root.version_no
                or (latest.structured_solution_spec_id == spec_id)
                != (latest.version_no == root.version_no)):
            raise RuntimeError("StructuredSolutionSpec validation root changed")
        try:
            draft = validate_structured_spec_draft(StructuredSpecDraftInput(
                project_id=project_id,
                spec_series_id=(series_id if root.version_no > 1 else None),
                supersedes_version_ref=root.supersedes_version_ref,
                spec_type=root.spec_type,
                payload=payload.payload_json,
                requirement_refs=tuple(SpecRequirementRef(
                    row.requirement_id, row.requirement_version_id)
                    for row in requirements),
                section_refs=tuple(SpecSectionRef(
                    row.solution_section_id, row.solution_section_version_id)
                    for row in sections),
                evidence_ids=tuple(row.evidence_id for row in evidence),
                artifact_ids=tuple(row.output_artifact_id for row in artifacts),
            ))
            if draft.payload_fingerprint != bytes(payload.payload_fingerprint):
                raise RuntimeError(
                    "StructuredSolutionSpec validation payload changed")
            snapshot = StructuredSpecValidationSnapshot(
                project_id=project_id,
                structured_solution_spec_id=spec_id,
                spec_series_id=series_id,
                spec_type=root.spec_type,
                version_no=root.version_no,
                version_state=root.version_state,
                content_fingerprint=bytes(root.content_fingerprint),
                payload_fingerprint=bytes(payload.payload_fingerprint),
                requirement_count=len(requirements),
                section_count=len(sections),
                evidence_count=len(evidence),
                artifact_count=len(artifacts),
            )
            return StructuredSpecValidationSource(
                snapshot, draft, latest.structured_solution_spec_id,
                latest.version_no)
        except StructuredSpecInputError:
            raise RuntimeError(
                "StructuredSolutionSpec validation source is invalid") from None

    @staticmethod
    def _rows(session, model, spec_id: uuid.UUID,
              series_id: uuid.UUID, project_id: uuid.UUID) -> tuple[object, ...]:
        return tuple(session.execute(select(model).where(
            model.structured_solution_spec_id == spec_id,
            model.spec_series_id == series_id,
            model.project_id == project_id,
        ).order_by(model.ordinal).with_for_update(
            read=True, of=model,
        ).execution_options(populate_existing=True)).scalars())
