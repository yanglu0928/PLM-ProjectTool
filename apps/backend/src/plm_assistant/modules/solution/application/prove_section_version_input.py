"""Compose current SectionVersion DRAFT sources in the caller's transaction.

This is a proof boundary, not a create command or a Review/Trace decision.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)

from .prove_section_document_content import SectionDocumentContentProof
from .prove_section_evidence_use import SectionEvidenceUseProof
from .section_version_base import CurrentSectionVersionBase, CurrentSectionVersionBasePort
from .section_version_input import (
    SectionVersionDraftInput,
    SectionVersionInputError,
    ValidatedSectionVersionDraft,
    validate_section_version_draft,
)


class SectionVersionInputProofError(RuntimeError):
    def __init__(self, code: str = "SOURCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProvenSectionVersionInput:
    draft: ValidatedSectionVersionDraft = field(repr=False)
    base: CurrentSectionVersionBase = field(repr=False)
    document: SectionDocumentContentProof = field(repr=False)
    requirements: tuple[OutlineApprovedRequirementProof, ...] = field(repr=False)
    evidence: tuple[SectionEvidenceUseProof, ...] = field(repr=False)
    content_fingerprint: bytes = field(repr=False)


class SectionDocumentPort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              document_version_id: uuid.UUID) -> SectionDocumentContentProof: ...


class SectionRequirementPort(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              requirement_id: uuid.UUID,
              requirement_version_id: uuid.UUID) -> OutlineApprovedRequirementProof: ...


class SectionEvidencePort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              evidence_id: uuid.UUID) -> SectionEvidenceUseProof: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


class SectionVersionInputProofService:
    def __init__(self, *, bases: CurrentSectionVersionBasePort,
                 documents: SectionDocumentPort,
                 requirements: SectionRequirementPort,
                 evidence: SectionEvidencePort) -> None:
        if any(port is None for port in (bases, documents, requirements, evidence)):
            raise ValueError("all current SectionVersion proof ports required")
        self._bases = bases
        self._documents = documents
        self._requirements = requirements
        self._evidence = evidence

    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID,
              draft: SectionVersionDraftInput) -> ProvenSectionVersionInput:
        if (transaction is None or type(session_token) is not bytes
                or len(session_token) != 32 or not _id(trace_id)):
            raise SectionVersionInputProofError("VALIDATION_FAILED")
        try:
            value = validate_section_version_draft(draft)
        except SectionVersionInputError:
            raise SectionVersionInputProofError("VALIDATION_FAILED") from None
        # OutputArtifact has no Owner proof yet. Never treat its UUID as content.
        if value.content_artifact_ref is not None:
            raise SectionVersionInputProofError()
        try:
            base = self._bases.current(
                transaction, project_id=value.project_id,
                section_id=value.solution_section_id)
            if (type(base) is not CurrentSectionVersionBase
                    or base.project_id != value.project_id
                    or base.solution_section_id != value.solution_section_id
                    or not _id(base.solution_outline_id)
                    or type(base.next_version_no) is not int
                    or not 1 <= base.next_version_no <= 2_147_483_647
                    or type(base.outline_lock_version) is not int
                    or base.outline_lock_version < 0
                    or type(base.section_lock_version) is not int
                    or base.section_lock_version < 0
                    or (base.next_version_no == 1
                        and base.supersedes_version_id is not None)
                    or (base.next_version_no > 1
                        and not _id(base.supersedes_version_id))):
                raise SectionVersionInputProofError()

            document_version_id = value.content_document_version_ref
            if not _id(document_version_id):
                raise SectionVersionInputProofError()
            document = self._documents.prove(
                transaction, session_token=session_token, trace_id=trace_id,
                project_id=value.project_id,
                document_version_id=document_version_id)
            if (type(document) is not SectionDocumentContentProof
                    or document.project_id != value.project_id
                    or not _id(document.document_id)
                    or document.document_version_id != document_version_id
                    or not _digest(document.content_sha256)):
                raise SectionVersionInputProofError()

            requirements = []
            requirement_facts = []
            for item in value.requirement_refs:
                proven = self._requirements.prove(
                    transaction, project_id=value.project_id,
                    requirement_id=item.requirement_id,
                    requirement_version_id=item.requirement_version_id)
                if (type(proven) is not OutlineApprovedRequirementProof
                        or proven.project_id != value.project_id
                        or proven.requirement_id != item.requirement_id
                        or proven.requirement_version_id != item.requirement_version_id
                        or type(proven.version_no) is not int
                        or proven.version_no < 1
                        or not _digest(proven.content_fingerprint)
                        or not _id(proven.review_id)
                        or not _id(proven.review_round_id)):
                    raise SectionVersionInputProofError()
                requirements.append(proven)
                requirement_facts.append([
                    str(item.requirement_id), str(item.requirement_version_id),
                    proven.version_no, proven.content_fingerprint.hex(),
                    str(proven.review_id), str(proven.review_round_id)])

            evidence = []
            evidence_facts = []
            for evidence_id in value.evidence_ids:
                proven_evidence = self._evidence.prove(
                    transaction, session_token=session_token, trace_id=trace_id,
                    project_id=value.project_id, evidence_id=evidence_id)
                if (type(proven_evidence) is not SectionEvidenceUseProof
                        or proven_evidence.project_id != value.project_id
                        or proven_evidence.evidence_id != evidence_id
                        or not _id(proven_evidence.document_id)
                        or not _id(proven_evidence.document_version_id)
                        or type(proven_evidence.observed_lock_version) is not int
                        or proven_evidence.observed_lock_version < 0
                        or not _digest(proven_evidence.content_fingerprint)):
                    raise SectionVersionInputProofError()
                evidence.append(proven_evidence)
                evidence_facts.append([
                    str(evidence_id), str(proven_evidence.document_id),
                    str(proven_evidence.document_version_id),
                    proven_evidence.observed_lock_version,
                    proven_evidence.content_fingerprint.hex()])

            content_fingerprint = canonical_payload_fingerprint({
                "kind": "SOLUTION_SECTION_VERSION_PROVEN_INPUT_V1",
                "request_fingerprint": value.request_fingerprint.hex(),
                "project_id": str(value.project_id),
                "solution_outline_id": str(base.solution_outline_id),
                "solution_section_id": str(value.solution_section_id),
                "version_no": base.next_version_no,
                "supersedes_version_id": (
                    str(base.supersedes_version_id)
                    if base.supersedes_version_id else None),
                "document": [str(document.document_id),
                             str(document.document_version_id),
                             document.content_sha256.hex()],
                "requirements": requirement_facts,
                "evidence": evidence_facts,
            })
            return ProvenSectionVersionInput(
                value, base, document, tuple(requirements), tuple(evidence),
                content_fingerprint)
        except SectionVersionInputProofError:
            raise
        except Exception:
            raise SectionVersionInputProofError() from None
