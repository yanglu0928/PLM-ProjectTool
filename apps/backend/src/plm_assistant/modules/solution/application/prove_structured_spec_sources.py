"""Same-transaction current source composition for a SOL-06 draft.

This is not a write, authorization, Trace, or Review decision.
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

from .prove_section_evidence_use import SectionEvidenceUseProof
from .prove_section_document_content import SectionDocumentContentProof
from .read_section import SectionCurrentView
from .read_section_version import SectionVersionHistoryView
from .structured_spec_input import (
    StructuredSpecDraftInput,
    StructuredSpecInputError,
    ValidatedStructuredSpecDraft,
    validate_structured_spec_draft,
)


class StructuredSpecSourceError(RuntimeError):
    def __init__(self, code: str = "SOURCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProvenStructuredSpecSources:
    draft: ValidatedStructuredSpecDraft = field(repr=False)
    requirements: tuple[OutlineApprovedRequirementProof, ...] = field(repr=False)
    sections: tuple[SectionVersionHistoryView, ...] = field(repr=False)
    evidence: tuple[SectionEvidenceUseProof, ...] = field(repr=False)
    content_fingerprint: bytes = field(repr=False)


class RequirementPort(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              requirement_id: uuid.UUID,
              requirement_version_id: uuid.UUID) -> OutlineApprovedRequirementProof: ...


class SectionPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID) -> SectionCurrentView | None: ...


class SectionVersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionHistoryView | None: ...

    def list(self, transaction: object, *, project_id: uuid.UUID,
             section_id: uuid.UUID, before_version_no: int | None,
             limit: int) -> tuple[SectionVersionHistoryView, ...]: ...


class EvidencePort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              evidence_id: uuid.UUID) -> SectionEvidenceUseProof: ...


class DocumentPort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              document_version_id: uuid.UUID) -> SectionDocumentContentProof: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


class StructuredSpecSourceProofService:
    def __init__(self, *, requirements: RequirementPort, sections: SectionPort,
                 versions: SectionVersionPort, evidence: EvidencePort,
                 documents: DocumentPort) -> None:
        if any(port is None for port in (
                requirements, sections, versions, evidence, documents)):
            raise ValueError("all SOL-06 source proof ports required")
        self._requirements = requirements
        self._sections = sections
        self._versions = versions
        self._evidence = evidence
        self._documents = documents

    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID,
              draft: StructuredSpecDraftInput) -> ProvenStructuredSpecSources:
        if (transaction is None or type(session_token) is not bytes
                or len(session_token) != 32 or not _id(trace_id)):
            raise StructuredSpecSourceError("VALIDATION_FAILED")
        try:
            value = validate_structured_spec_draft(draft)
        except StructuredSpecInputError:
            raise StructuredSpecSourceError("VALIDATION_FAILED") from None
        # No OutputArtifact Owner/target table exists yet. Never accept an ID alone.
        if value.artifact_ids:
            raise StructuredSpecSourceError()
        try:
            requirements: list[OutlineApprovedRequirementProof] = []
            requirement_facts: list[list[object]] = []
            for ref in value.requirement_refs:
                proof = self._requirements.prove(
                    transaction, project_id=value.project_id,
                    requirement_id=ref.requirement_id,
                    requirement_version_id=ref.requirement_version_id)
                if (type(proof) is not OutlineApprovedRequirementProof
                        or proof.project_id != value.project_id
                        or proof.requirement_id != ref.requirement_id
                        or proof.requirement_version_id != ref.requirement_version_id
                        or type(proof.version_no) is not int or proof.version_no < 1
                        or not _digest(proof.content_fingerprint)
                        or not _id(proof.review_id) or not _id(proof.review_round_id)):
                    raise StructuredSpecSourceError()
                requirements.append(proof)
                requirement_facts.append([
                    str(ref.requirement_id), str(ref.requirement_version_id),
                    proof.version_no, proof.content_fingerprint.hex(),
                    str(proof.review_id), str(proof.review_round_id)])

            sections: list[SectionVersionHistoryView] = []
            section_facts: list[list[object]] = []
            for ref in value.section_refs:
                root = self._sections.get_current(
                    transaction, project_id=value.project_id,
                    section_id=ref.solution_section_id)
                version = self._versions.get(
                    transaction, project_id=value.project_id,
                    section_id=ref.solution_section_id,
                    version_id=ref.solution_section_version_id)
                if (type(root) is not SectionCurrentView
                        or root.project_id != value.project_id
                        or root.solution_section_id != ref.solution_section_id
                        or root.section_state != "ACTIVE"
                        or type(version) is not SectionVersionHistoryView
                        or version.project_id != value.project_id
                        or version.solution_section_id != ref.solution_section_id
                        or version.solution_section_version_id != ref.solution_section_version_id
                        or version.version_state not in ("DRAFT", "IN_REVIEW", "APPROVED")
                        or type(version.version_no) is not int or version.version_no < 1
                        or not _digest(version.content_fingerprint)
                        or (version.version_state == "DRAFT" and (
                            version.review_ref is not None
                            or version.review_round_ref is not None))
                        or (version.version_state == "IN_REVIEW" and (
                            not _id(version.review_ref)
                            or not _id(version.review_round_ref)))
                        or version.content_artifact_ref is not None
                        or not _id(version.content_document_version_ref)):
                    raise StructuredSpecSourceError()
                if version.version_state == "APPROVED":
                    if (root.current_approved_version_ref != ref.solution_section_version_id
                            or not _id(version.review_ref)
                            or not _id(version.review_round_ref)):
                        raise StructuredSpecSourceError()
                else:
                    latest = self._versions.list(
                        transaction, project_id=value.project_id,
                        section_id=ref.solution_section_id,
                        before_version_no=None, limit=1)
                    if (type(latest) is not tuple or len(latest) != 1
                            or type(latest[0]) is not SectionVersionHistoryView
                            or latest[0].solution_section_version_id
                            != ref.solution_section_version_id):
                        raise StructuredSpecSourceError()
                document = self._documents.prove(
                    transaction, session_token=session_token, trace_id=trace_id,
                    project_id=value.project_id,
                    document_version_id=version.content_document_version_ref)
                if (type(document) is not SectionDocumentContentProof
                        or document.project_id != value.project_id
                        or not _id(document.document_id)
                        or document.document_version_id != version.content_document_version_ref
                        or not _digest(document.content_sha256)):
                    raise StructuredSpecSourceError()
                sections.append(version)
                section_facts.append([
                    str(ref.solution_section_id), str(ref.solution_section_version_id),
                    version.version_no, version.version_state,
                    version.content_fingerprint.hex(),
                    str(document.document_id),
                    str(document.document_version_id),
                    document.content_sha256.hex(),
                    str(version.review_ref) if version.review_ref else None,
                    str(version.review_round_ref) if version.review_round_ref else None])

            evidence: list[SectionEvidenceUseProof] = []
            evidence_facts: list[list[object]] = []
            for evidence_id in value.evidence_ids:
                proof = self._evidence.prove(
                    transaction, session_token=session_token, trace_id=trace_id,
                    project_id=value.project_id, evidence_id=evidence_id)
                if (type(proof) is not SectionEvidenceUseProof
                        or proof.project_id != value.project_id
                        or proof.evidence_id != evidence_id
                        or not _id(proof.document_id)
                        or not _id(proof.document_version_id)
                        or type(proof.observed_lock_version) is not int
                        or proof.observed_lock_version < 0
                        or not _digest(proof.content_fingerprint)):
                    raise StructuredSpecSourceError()
                evidence.append(proof)
                evidence_facts.append([
                    str(evidence_id), str(proof.document_id),
                    str(proof.document_version_id), proof.observed_lock_version,
                    proof.content_fingerprint.hex()])

            fingerprint = canonical_payload_fingerprint({
                "kind": "STRUCTURED_SPEC_PROVEN_SOURCES_V1",
                "request_fingerprint": value.request_fingerprint.hex(),
                "project_id": str(value.project_id),
                "requirements": requirement_facts,
                "sections": section_facts,
                "evidence": evidence_facts,
            })
            return ProvenStructuredSpecSources(
                value, tuple(requirements), tuple(sections), tuple(evidence),
                fingerprint)
        except StructuredSpecSourceError:
            raise
        except Exception:
            raise StructuredSpecSourceError() from None
