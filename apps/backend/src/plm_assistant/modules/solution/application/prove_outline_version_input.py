"""Same-transaction current input proof for a DRAFT OutlineVersion write."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)

from .outline_version_input import (
    OutlineVersionDraftInput,
    OutlineVersionInputError,
    ValidatedOutlineVersionDraft,
    validate_outline_version_draft,
)
from .prove_outline_section_use import OutlineSectionUseProof
from .prove_reference_use import (
    EligibleReferenceUseProof,
    ReferenceUseQuery,
)


class OutlineVersionInputProofError(RuntimeError):
    def __init__(self, code: str = "SOURCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CurrentOutlineVersionBase:
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    next_version_no: int
    supersedes_version_id: uuid.UUID | None
    root_lock_version: int


@dataclass(frozen=True, slots=True)
class ProvenOutlineVersionInput:
    draft: ValidatedOutlineVersionDraft = field(repr=False)
    next_version_no: int
    supersedes_version_id: uuid.UUID | None
    root_lock_version: int
    content_fingerprint: bytes = field(repr=False)


class CurrentBasePort(Protocol):
    def current(self, transaction: object, *, project_id: uuid.UUID,
                outline_id: uuid.UUID) -> CurrentOutlineVersionBase | None: ...


class SectionPort(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              outline_id: uuid.UUID, section_id: uuid.UUID) -> OutlineSectionUseProof: ...


class RequirementPort(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              requirement_id: uuid.UUID,
              requirement_version_id: uuid.UUID) -> OutlineApprovedRequirementProof: ...


class ReferencePort(Protocol):
    def prove(self, transaction: object,
              query: ReferenceUseQuery) -> EligibleReferenceUseProof: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class OutlineVersionInputProofService:
    def __init__(self, *, bases: CurrentBasePort, sections: SectionPort,
                 requirements: RequirementPort, references: ReferencePort) -> None:
        if any(port is None for port in (bases, sections, requirements, references)):
            raise ValueError("all current OutlineVersion input ports required")
        self._bases = bases
        self._sections = sections
        self._requirements = requirements
        self._references = references

    def prove(self, transaction: object, *, trace_id: uuid.UUID,
              draft: OutlineVersionDraftInput) -> ProvenOutlineVersionInput:
        if transaction is None or not _id(trace_id):
            raise OutlineVersionInputProofError("VALIDATION_FAILED")
        try:
            value = validate_outline_version_draft(draft)
        except OutlineVersionInputError:
            raise OutlineVersionInputProofError("VALIDATION_FAILED") from None
        try:
            base = self._bases.current(
                transaction, project_id=value.project_id,
                outline_id=value.solution_outline_id)
            if (type(base) is not CurrentOutlineVersionBase
                    or base.project_id != value.project_id
                    or base.solution_outline_id != value.solution_outline_id
                    or type(base.next_version_no) is not int
                    or not 1 <= base.next_version_no <= 2_147_483_647
                    or type(base.root_lock_version) is not int
                    or base.root_lock_version < 0
                    or (base.next_version_no == 1
                        and base.supersedes_version_id is not None)
                    or (base.next_version_no > 1
                        and not _id(base.supersedes_version_id))):
                raise OutlineVersionInputProofError()
            sections = []
            for section_id in value.section_ids:
                proof = self._sections.prove(
                    transaction, project_id=value.project_id,
                    outline_id=value.solution_outline_id, section_id=section_id)
                if (type(proof) is not OutlineSectionUseProof
                        or proof.project_id != value.project_id
                        or proof.solution_outline_id != value.solution_outline_id
                        or proof.solution_section_id != section_id):
                    raise OutlineVersionInputProofError()
                sections.append(str(section_id))
            requirements = []
            for item in value.requirement_refs:
                proof = self._requirements.prove(
                    transaction, project_id=value.project_id,
                    requirement_id=item.requirement_id,
                    requirement_version_id=item.requirement_version_id)
                if (type(proof) is not OutlineApprovedRequirementProof
                        or proof.project_id != value.project_id
                        or proof.requirement_id != item.requirement_id
                        or proof.requirement_version_id != item.requirement_version_id
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32
                        or not _id(proof.review_id)
                        or not _id(proof.review_round_id)):
                    raise OutlineVersionInputProofError()
                requirements.append([
                    str(item.requirement_id), str(item.requirement_version_id),
                    proof.content_fingerprint.hex(), str(proof.review_id),
                    str(proof.review_round_id)])
            references = []
            for item in value.reference_refs:
                proof = self._references.prove(
                    transaction, ReferenceUseQuery(
                        trace_id, value.project_id,
                        item.reference_solution_id,
                        item.reference_version_id, item.scope))
                if (type(proof) is not EligibleReferenceUseProof
                        or proof.target_project_id != value.project_id
                        or proof.scope != item.scope
                        or proof.reference_solution_id != item.reference_solution_id
                        or proof.reference_version_id != item.reference_version_id
                        or type(proof.source_fingerprint) is not bytes
                        or len(proof.source_fingerprint) != 32
                        or not _id(proof.eligibility_event_id)
                        or (item.scope == "PROJECT"
                            and proof.deidentification_confirmation_id is not None)
                        or (item.scope == "GLOBAL"
                            and not _id(proof.deidentification_confirmation_id))):
                    raise OutlineVersionInputProofError()
                references.append([
                    item.scope, str(item.reference_solution_id),
                    str(item.reference_version_id), proof.source_fingerprint.hex(),
                    str(proof.eligibility_event_id),
                    str(proof.deidentification_confirmation_id)
                    if proof.deidentification_confirmation_id else None])
            content_fingerprint = canonical_payload_fingerprint({
                "project_id": str(value.project_id),
                "solution_outline_id": str(value.solution_outline_id),
                "version_no": base.next_version_no,
                "supersedes_version_id": str(base.supersedes_version_id)
                if base.supersedes_version_id else None,
                "sections": sections,
                "requirements": requirements,
                "references": references,
                "missing_declarations": value.missing_declarations(),
                "conflict_declarations": value.conflict_declarations(),
            })
            return ProvenOutlineVersionInput(
                value, base.next_version_no, base.supersedes_version_id,
                base.root_lock_version, content_fingerprint)
        except OutlineVersionInputProofError:
            raise
        except Exception:
            raise OutlineVersionInputProofError() from None
