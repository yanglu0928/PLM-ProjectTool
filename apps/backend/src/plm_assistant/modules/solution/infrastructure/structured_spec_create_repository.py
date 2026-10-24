"""Persist one complete SOL-06 DRAFT set in the caller's transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, text

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.solution.application.prove_structured_spec_sources import (
    ProvenStructuredSpecSources,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef,
)
from plm_assistant.modules.solution.application.structured_spec_payload import (
    StructuredSpecPayloadError, validate_structured_spec_payload,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecInitialView, StructuredSpecRevisionBase,
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
    if tuple(item.ordinal for item in rows) != tuple(range(1, len(rows) + 1)):
        raise RuntimeError("StructuredSolutionSpec fixed collection is incomplete")


class SqlAlchemyStructuredSpecCreateRepository:
    def revision_base(self, transaction: object, *, project_id: uuid.UUID,
                      spec_id: uuid.UUID) -> StructuredSpecRevisionBase | None:
        if not _id(project_id) or not _id(spec_id):
            return None
        session = _session(transaction)
        identity = session.execute(select(
            Root.spec_series_id,
        ).where(
            Root.structured_solution_spec_id == spec_id,
            Root.project_id == project_id,
        )).one_or_none()
        if identity is None:
            return None
        series_id = identity.spec_series_id
        if not _id(series_id):
            raise RuntimeError("StructuredSolutionSpec revision base is inconsistent")
        session.execute(text(
            "SELECT pg_advisory_xact_lock(hashtextextended("
            "'plm.sol_structured_specs:' || CAST(:series_id AS text),0))"),
            {"series_id": series_id})
        requested = session.execute(select(Root).where(
            Root.structured_solution_spec_id == spec_id,
            Root.project_id == project_id,
            Root.spec_series_id == series_id,
        ).with_for_update(read=True, of=Root)).scalar_one_or_none()
        latest = session.execute(select(Root).where(
            Root.project_id == project_id,
            Root.spec_series_id == series_id,
        ).order_by(Root.version_no.desc()).limit(1)
            .with_for_update(read=True, of=Root)).scalar_one_or_none()
        states = {
            "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
            "SUPERSEDED", "RESTRICTED",
        }
        if (requested is None or latest is None
                or requested.project_id != project_id
                or latest.project_id != project_id
                or requested.spec_series_id != series_id
                or latest.spec_series_id != series_id
                or requested.spec_type != latest.spec_type
                or requested.version_no < 1
                or latest.version_no < requested.version_no
                or requested.version_state not in states
                or latest.version_state not in states
                or (requested.supersedes_version_ref is None)
                != (requested.version_no == 1)
                or (latest.supersedes_version_ref is None)
                != (latest.version_no == 1)
                or (latest.structured_solution_spec_id == spec_id)
                != (latest.version_no == requested.version_no)):
            raise RuntimeError("StructuredSolutionSpec revision base is inconsistent")
        return StructuredSpecRevisionBase(
            requested.structured_solution_spec_id,
            latest.structured_solution_spec_id,
            series_id, project_id, requested.spec_type,
            requested.version_no, latest.version_no,
            requested.version_state,
        )

    def revise(self, transaction: object, *, base: StructuredSpecRevisionBase,
               version_id: uuid.UUID, actor_id: uuid.UUID,
               proof: ProvenStructuredSpecSources) -> StructuredSpecInitialView:
        if (type(base) is not StructuredSpecRevisionBase
                or not _id(version_id) or not _id(actor_id)
                or type(proof) is not ProvenStructuredSpecSources):
            raise ValueError("invalid StructuredSolutionSpec revise input")
        draft = proof.draft
        if (base.latest_version_ref != base.structured_solution_spec_id
                or base.version_state not in {"DRAFT", "RETURNED", "APPROVED"}):
            raise RuntimeError("StructuredSolutionSpec revision conflict")
        if (draft.project_id != base.project_id
                or draft.spec_series_id != base.spec_series_id
                or draft.supersedes_version_ref
                != base.structured_solution_spec_id
                or draft.spec_type != base.spec_type):
            raise ValueError("StructuredSolutionSpec revision binding changed")
        result = self.create(
            transaction, version_id=version_id,
            actor_id=actor_id, proof=proof)
        if (result.project_id != base.project_id
                or result.spec_series_id != base.spec_series_id
                or result.spec_type != base.spec_type
                or result.version_no != base.version_no + 1
                or result.supersedes_version_ref
                != base.structured_solution_spec_id):
            raise RuntimeError("StructuredSolutionSpec revision result changed")
        return result

    def create(self, transaction: object, *, version_id: uuid.UUID,
               actor_id: uuid.UUID,
               proof: ProvenStructuredSpecSources) -> StructuredSpecInitialView:
        if (not _id(version_id) or not _id(actor_id)
                or type(proof) is not ProvenStructuredSpecSources
                or len(proof.content_fingerprint) != 32):
            raise ValueError("invalid StructuredSolutionSpec create input")
        draft = proof.draft
        if draft.artifact_ids:
            raise ValueError("OutputArtifact Owner is not installed")
        session = _session(transaction)
        series_id = draft.spec_series_id or uuid.UUID(new_uuid7())
        session.execute(text(
            "SELECT pg_advisory_xact_lock(hashtextextended("
            "'plm.sol_structured_specs:' || CAST(:series_id AS text),0))"),
            {"series_id": series_id})
        latest = session.execute(select(Root).where(
            Root.spec_series_id == series_id,
        ).order_by(Root.version_no.desc()).limit(1).with_for_update()).scalar_one_or_none()
        if latest is None:
            if draft.supersedes_version_ref is not None:
                raise RuntimeError("StructuredSolutionSpec series does not exist")
            version_no, supersedes = 1, None
        else:
            if (latest.project_id != draft.project_id
                    or latest.spec_type != draft.spec_type
                    or latest.structured_solution_spec_id != draft.supersedes_version_ref
                    or latest.version_no >= 2_147_483_647):
                raise RuntimeError("StructuredSolutionSpec series changed")
            version_no, supersedes = latest.version_no + 1, latest.structured_solution_spec_id
        session.execute(insert(Root).values(
            structured_solution_spec_id=version_id,
            spec_series_id=series_id, project_id=draft.project_id,
            spec_type=draft.spec_type, version_no=version_no,
            version_state="DRAFT", content_fingerprint=proof.content_fingerprint,
            supersedes_version_ref=supersedes,
            review_ref=None, review_round_ref=None, created_by=actor_id,
        ))
        session.execute(insert(Payload).values(
            structured_solution_spec_id=version_id,
            spec_series_id=series_id, project_id=draft.project_id,
            spec_type=draft.spec_type, schema_version=1,
            payload_json=draft.payload(),
            payload_fingerprint=draft.payload_fingerprint,
        ))
        for ordinal, ref in enumerate(draft.requirement_refs, 1):
            session.execute(insert(RequirementRef).values(
                structured_solution_spec_id=version_id,
                spec_series_id=series_id, project_id=draft.project_id,
                requirement_id=ref.requirement_id,
                requirement_version_id=ref.requirement_version_id,
                ordinal=ordinal))
        for ordinal, ref in enumerate(draft.section_refs, 1):
            session.execute(insert(SectionRef).values(
                structured_solution_spec_id=version_id,
                spec_series_id=series_id, project_id=draft.project_id,
                solution_section_id=ref.solution_section_id,
                solution_section_version_id=ref.solution_section_version_id,
                ordinal=ordinal))
        for ordinal, evidence_id in enumerate(draft.evidence_ids, 1):
            session.execute(insert(EvidenceRef).values(
                structured_solution_spec_id=version_id,
                spec_series_id=series_id, project_id=draft.project_id,
                evidence_id=evidence_id, ordinal=ordinal))
        result = self.first_result(
            transaction, version_id=version_id, project_id=draft.project_id)
        if result is None or result.created_by != actor_id:
            raise RuntimeError("StructuredSolutionSpec first result is missing")
        return result

    def first_result(self, transaction: object, *, version_id: uuid.UUID,
                     project_id: uuid.UUID) -> StructuredSpecInitialView | None:
        if not _id(version_id) or not _id(project_id):
            return None
        session = _session(transaction)
        pair = session.execute(select(Root, Payload).join(
            Payload, Payload.structured_solution_spec_id
            == Root.structured_solution_spec_id,
        ).where(
            Root.structured_solution_spec_id == version_id,
            Root.project_id == project_id,
        ).with_for_update(read=True, of=Root)).one_or_none()
        if pair is None:
            exists = session.execute(select(Root.structured_solution_spec_id).where(
                Root.structured_solution_spec_id == version_id,
                Root.project_id == project_id,
            )).scalar_one_or_none()
            if exists is not None:
                raise RuntimeError("StructuredSolutionSpec payload is missing")
            return None
        root, payload = pair
        requirements = tuple(session.execute(select(RequirementRef).where(
            RequirementRef.structured_solution_spec_id == version_id,
            RequirementRef.spec_series_id == root.spec_series_id,
            RequirementRef.project_id == project_id,
        ).order_by(RequirementRef.ordinal)).scalars())
        sections = tuple(session.execute(select(SectionRef).where(
            SectionRef.structured_solution_spec_id == version_id,
            SectionRef.spec_series_id == root.spec_series_id,
            SectionRef.project_id == project_id,
        ).order_by(SectionRef.ordinal)).scalars())
        evidence = tuple(session.execute(select(EvidenceRef).where(
            EvidenceRef.structured_solution_spec_id == version_id,
            EvidenceRef.spec_series_id == root.spec_series_id,
            EvidenceRef.project_id == project_id,
        ).order_by(EvidenceRef.ordinal)).scalars())
        artifacts = tuple(session.execute(select(ArtifactRef.output_artifact_id).where(
            ArtifactRef.structured_solution_spec_id == version_id,
        )).scalars())
        _ordered(requirements)
        _ordered(sections)
        _ordered(evidence)
        if (not requirements or not sections or artifacts
                or payload.spec_series_id != root.spec_series_id
                or payload.project_id != project_id
                or payload.spec_type != root.spec_type
                or payload.schema_version != 1
                or root.version_no < 1
                or not _id(root.created_by)
                or len(root.content_fingerprint) != 32
                or len(payload.payload_fingerprint) != 32
                or (root.supersedes_version_ref is None) != (root.version_no == 1)
                or len({item.requirement_id for item in requirements}) != len(requirements)
                or len({item.requirement_version_id for item in requirements}) != len(requirements)
                or len({item.solution_section_id for item in sections}) != len(sections)
                or len({item.solution_section_version_id for item in sections}) != len(sections)
                or len({item.evidence_id for item in evidence}) != len(evidence)):
            raise RuntimeError("StructuredSolutionSpec history is inconsistent")
        try:
            validated = validate_structured_spec_payload(root.spec_type, payload.payload_json)
        except StructuredSpecPayloadError:
            raise RuntimeError("StructuredSolutionSpec payload is invalid") from None
        if validated.payload_fingerprint != payload.payload_fingerprint:
            raise RuntimeError("StructuredSolutionSpec payload fingerprint changed")
        return StructuredSpecInitialView(
            version_id, root.spec_series_id, project_id, root.spec_type,
            root.version_no, root.content_fingerprint, validated.payload_json,
            payload.payload_fingerprint,
            tuple(SpecRequirementRef(item.requirement_id,
                                     item.requirement_version_id)
                  for item in requirements),
            tuple(SpecSectionRef(item.solution_section_id,
                                 item.solution_section_version_id)
                  for item in sections),
            tuple(item.evidence_id for item in evidence),
            root.supersedes_version_ref, root.created_by, root.created_at,
        )
