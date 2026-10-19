"""Read-only current-fact evaluation for one locked SOL-06 version."""

from __future__ import annotations

import uuid
from typing import Protocol

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, canonical_payload_fingerprint,
)

from .prove_section_document_content import SectionDocumentContentProof
from .prove_section_evidence_use import SectionEvidenceUseProof
from .read_section import SectionCurrentView
from .read_section_version import SectionVersionHistoryView
from .structured_spec_validation_contract import (
    StructuredSpecValidationFacts, StructuredSpecValidationObservation,
    ValidateStructuredSpec, build_structured_spec_type_checks,
)
from .structured_spec_validation_source import StructuredSpecValidationSource


class StructuredSpecCurrentFactsError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


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


_STRUCTURAL_CHECK = {
    "PROCESS_MODEL": "GRAPH_STRUCTURE",
    "INTERFACE_SPEC": "BOUNDARY_MAPPING",
    "MIGRATION_SPEC": "SCOPE_MAPPING",
    "PERMISSION_DESIGN": "MATRIX_DEFAULT_DENY",
}


class StructuredSpecCurrentFactEvaluator:
    """Evaluate only installed Owners; absence stays UNAVAILABLE."""

    def __init__(self, *, requirements: RequirementPort, sections: SectionPort,
                 versions: SectionVersionPort, evidence: EvidencePort,
                 documents: DocumentPort) -> None:
        if any(port is None for port in (
                requirements, sections, versions, evidence, documents)):
            raise ValueError("all SOL-06 current fact ports required")
        self._requirements = requirements
        self._sections = sections
        self._versions = versions
        self._evidence = evidence
        self._documents = documents

    def evaluate(
        self, transaction: object, *, command: ValidateStructuredSpec,
        source: StructuredSpecValidationSource,
    ) -> StructuredSpecValidationObservation:
        if (transaction is None or type(command) is not ValidateStructuredSpec
                or type(source) is not StructuredSpecValidationSource
                or (command.project_id,
                    command.structured_solution_spec_id) != (
                        source.snapshot.project_id,
                        source.snapshot.structured_solution_spec_id)):
            raise StructuredSpecCurrentFactsError("VALIDATION_FAILED")
        requirements, requirement_facts = self._requirement_status(
            transaction, source)
        sections, section_facts = self._section_status(
            transaction, command, source)
        evidence, evidence_facts = self._evidence_status(
            transaction, command, source)
        integrity = "UNAVAILABLE"
        if (requirements, sections, evidence) == ("PASS", "PASS", "PASS"):
            try:
                current = canonical_payload_fingerprint({
                    "kind": "STRUCTURED_SPEC_PROVEN_SOURCES_V1",
                    "request_fingerprint": source.draft.request_fingerprint.hex(),
                    "project_id": str(source.snapshot.project_id),
                    "requirements": requirement_facts,
                    "sections": section_facts,
                    "evidence": evidence_facts,
                })
                integrity = ("PASS" if current
                             == source.snapshot.content_fingerprint else "FAIL")
            except IdempotencyError:
                raise StructuredSpecCurrentFactsError() from None
        facts = StructuredSpecValidationFacts(
            integrity=integrity, payload="PASS",
            requirements=requirements, sections=sections, evidence=evidence,
            artifacts=("PASS" if not source.draft.artifact_ids
                       else "UNAVAILABLE"),
            trace="UNAVAILABLE",
            current_version=("PASS" if source.is_current_version else "FAIL"),
        )
        checks = build_structured_spec_type_checks(source.snapshot.spec_type)
        structural = _STRUCTURAL_CHECK[source.snapshot.spec_type]
        statuses = {item.code: ("PASS" if item.code == structural
                                else "UNAVAILABLE")
                    for item in checks.checks}
        return StructuredSpecValidationObservation(
            facts, build_structured_spec_type_checks(
                source.snapshot.spec_type, statuses))

    def _requirement_status(
        self, transaction: object, source: StructuredSpecValidationSource,
    ) -> tuple[str, list[list[object]]]:
        facts: list[list[object]] = []
        for ref in source.draft.requirement_refs:
            try:
                proof = self._requirements.prove(
                    transaction, project_id=source.snapshot.project_id,
                    requirement_id=ref.requirement_id,
                    requirement_version_id=ref.requirement_version_id)
            except Exception:
                return "UNAVAILABLE", []
            if (type(proof) is not OutlineApprovedRequirementProof
                    or proof.project_id != source.snapshot.project_id
                    or proof.requirement_id != ref.requirement_id
                    or proof.requirement_version_id != ref.requirement_version_id
                    or type(proof.version_no) is not int or proof.version_no < 1
                    or not _digest(proof.content_fingerprint)
                    or not _id(proof.review_id)
                    or not _id(proof.review_round_id)):
                return "UNAVAILABLE", []
            facts.append([
                str(ref.requirement_id), str(ref.requirement_version_id),
                proof.version_no, proof.content_fingerprint.hex(),
                str(proof.review_id), str(proof.review_round_id)])
        return "PASS", facts

    def _section_status(
        self, transaction: object, command: ValidateStructuredSpec,
        source: StructuredSpecValidationSource,
    ) -> tuple[str, list[list[object]]]:
        facts: list[list[object]] = []
        for ref in source.draft.section_refs:
            try:
                root = self._sections.get_current(
                    transaction, project_id=source.snapshot.project_id,
                    section_id=ref.solution_section_id)
                version = self._versions.get(
                    transaction, project_id=source.snapshot.project_id,
                    section_id=ref.solution_section_id,
                    version_id=ref.solution_section_version_id)
                if (type(root) is not SectionCurrentView
                        or root.project_id != source.snapshot.project_id
                        or root.solution_section_id != ref.solution_section_id
                        or root.section_state != "ACTIVE"
                        or type(version) is not SectionVersionHistoryView
                        or version.project_id != source.snapshot.project_id
                        or version.solution_section_id != ref.solution_section_id
                        or version.solution_section_version_id
                        != ref.solution_section_version_id
                        or version.version_state not in (
                            "DRAFT", "IN_REVIEW", "APPROVED")
                        or type(version.version_no) is not int
                        or version.version_no < 1
                        or not _digest(version.content_fingerprint)
                        or version.content_artifact_ref is not None
                        or not _id(version.content_document_version_ref)):
                    return "UNAVAILABLE", []
                if version.version_state == "APPROVED":
                    if (root.current_approved_version_ref
                            != ref.solution_section_version_id
                            or not _id(version.review_ref)
                            or not _id(version.review_round_ref)):
                        return "UNAVAILABLE", []
                else:
                    if (version.version_state == "DRAFT" and (
                            version.review_ref is not None
                            or version.review_round_ref is not None)):
                        return "UNAVAILABLE", []
                    if (version.version_state == "IN_REVIEW" and (
                            not _id(version.review_ref)
                            or not _id(version.review_round_ref))):
                        return "UNAVAILABLE", []
                    latest = self._versions.list(
                        transaction, project_id=source.snapshot.project_id,
                        section_id=ref.solution_section_id,
                        before_version_no=None, limit=1)
                    if (type(latest) is not tuple or len(latest) != 1
                            or type(latest[0]) is not SectionVersionHistoryView
                            or latest[0].solution_section_version_id
                            != ref.solution_section_version_id):
                        return "UNAVAILABLE", []
                document = self._documents.prove(
                    transaction, session_token=command.session_token,
                    trace_id=command.trace_id,
                    project_id=source.snapshot.project_id,
                    document_version_id=version.content_document_version_ref)
                if (type(document) is not SectionDocumentContentProof
                        or document.project_id != source.snapshot.project_id
                        or not _id(document.document_id)
                        or document.document_version_id
                        != version.content_document_version_ref
                        or not _digest(document.content_sha256)):
                    return "UNAVAILABLE", []
                facts.append([
                    str(ref.solution_section_id),
                    str(ref.solution_section_version_id),
                    version.version_no, version.version_state,
                    version.content_fingerprint.hex(), str(document.document_id),
                    str(document.document_version_id),
                    document.content_sha256.hex(),
                    str(version.review_ref) if version.review_ref else None,
                    (str(version.review_round_ref)
                     if version.review_round_ref else None)])
            except Exception:
                return "UNAVAILABLE", []
        return "PASS", facts

    def _evidence_status(
        self, transaction: object, command: ValidateStructuredSpec,
        source: StructuredSpecValidationSource,
    ) -> tuple[str, list[list[object]]]:
        facts: list[list[object]] = []
        for evidence_id in source.draft.evidence_ids:
            try:
                proof = self._evidence.prove(
                    transaction, session_token=command.session_token,
                    trace_id=command.trace_id,
                    project_id=source.snapshot.project_id,
                    evidence_id=evidence_id)
            except Exception:
                return "UNAVAILABLE", []
            if (type(proof) is not SectionEvidenceUseProof
                    or proof.project_id != source.snapshot.project_id
                    or proof.evidence_id != evidence_id
                    or not _id(proof.document_id)
                    or not _id(proof.document_version_id)
                    or type(proof.observed_lock_version) is not int
                    or proof.observed_lock_version < 0
                    or not _digest(proof.content_fingerprint)):
                return "UNAVAILABLE", []
            facts.append([
                str(evidence_id), str(proof.document_id),
                str(proof.document_version_id), proof.observed_lock_version,
                proof.content_fingerprint.hex()])
        return "PASS", facts
