"""Authorized first-observation SectionVersion validation; no Review mutation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)
from plm_assistant.modules.trace.application.implements_coverage import (
    TraceImplementsCoverageError, TraceImplementsCoverageProof,
)
from plm_assistant.modules.trace.application.target_proof import TraceProofQuery
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef

from .prove_section_document_content import SectionDocumentContentProof
from .prove_section_evidence_use import SectionEvidenceUseProof
from .qualify_section_structured_spec import QualifiedSectionStructuredSpec
from .read_section import SectionCurrentView
from .read_section_version import SectionVersionHistoryView
from .section_version_input import (
    SectionStructuredSpecRef, is_normalized_spec_basis,
)
from .section_version_validation_contract import (
    AUDIT_ACTION, OPERATION, SectionVersionValidationFacts,
    SectionVersionValidationReport, SectionVersionValidationSnapshot,
    ValidateSectionVersion, audit_reason_for_facts,
    build_section_version_validation_report, facts_from_audit_reason,
)


class SectionVersionValidationError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SectionVersionValidationAudit:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    observed_at: datetime
    reason_code: str
    before_state: str


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SectionPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID) -> SectionCurrentView | None: ...


class VersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionHistoryView | None: ...


class DocumentPort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              document_version_id: uuid.UUID) -> SectionDocumentContentProof: ...


class RequirementPort(Protocol):
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              requirement_id: uuid.UUID,
              requirement_version_id: uuid.UUID) -> OutlineApprovedRequirementProof: ...


class EvidencePort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              evidence_id: uuid.UUID) -> SectionEvidenceUseProof: ...


class TracePort(Protocol):
    def prove(self, transaction: object, *, query: TraceProofQuery,
              target: TraceVersionRef,
              requirement_refs: tuple[TraceVersionRef, ...],
              ) -> TraceImplementsCoverageProof: ...


class CurrentSpecPort(Protocol):
    """Re-observe current approved Spec and exact Review facts in this transaction."""

    def prove(self, transaction: object, *,
              version: SectionVersionHistoryView,
              ) -> tuple[QualifiedSectionStructuredSpec, ...]: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AuditSourcePort(Protocol):
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionValidationAudit | None: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class SectionVersionCurrentValidator:
    """Current source proofs; absent Trace/Spec Owners remain UNAVAILABLE."""

    def __init__(self, *, documents: DocumentPort,
                 requirements: RequirementPort,
                 evidence: EvidencePort,
                 trace: TracePort | None = None,
                 specs: CurrentSpecPort | None = None) -> None:
        if any(port is None for port in (documents, requirements, evidence)):
            raise ValueError("SectionVersion current source ports required")
        self._documents, self._requirements, self._evidence = (
            documents, requirements, evidence)
        self._trace = trace
        self._specs = specs

    def facts(self, transaction: object, *, command: ValidateSectionVersion,
              version: SectionVersionHistoryView) -> SectionVersionValidationFacts:
        if (transaction is None or type(command) is not ValidateSectionVersion
                or type(version) is not SectionVersionHistoryView
                or (version.project_id, version.solution_section_id,
                    version.solution_section_version_id) != (
                        command.project_id, command.solution_section_id,
                        command.solution_section_version_id)):
            raise SectionVersionValidationError()
        content = "UNAVAILABLE"
        document_id = version.content_document_version_ref
        if _id(document_id) and version.content_artifact_ref is None:
            try:
                proof = self._documents.prove(
                    transaction, session_token=command.session_token,
                    trace_id=command.trace_id, project_id=command.project_id,
                    document_version_id=document_id)
                if (type(proof) is SectionDocumentContentProof
                        and proof.project_id == command.project_id
                        and _id(proof.document_id)
                        and proof.document_version_id == document_id
                        and type(proof.content_sha256) is bytes
                        and len(proof.content_sha256) == 32):
                    content = "PASS"
            except Exception:
                pass  # An opaque source failure is not evidence of current eligibility.
        requirements = "PASS"
        for ref in version.requirement_refs:
            try:
                proof = self._requirements.prove(
                    transaction, project_id=command.project_id,
                    requirement_id=ref.requirement_id,
                    requirement_version_id=ref.requirement_version_id)
                if (type(proof) is not OutlineApprovedRequirementProof
                        or proof.project_id != command.project_id
                        or proof.requirement_id != ref.requirement_id
                        or proof.requirement_version_id != ref.requirement_version_id
                        or type(proof.version_no) is not int or proof.version_no < 1
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32
                        or not _id(proof.review_id) or not _id(proof.review_round_id)):
                    requirements = "UNAVAILABLE"
            except Exception:
                requirements = "UNAVAILABLE"
        evidence = "PASS"
        for evidence_id in version.evidence_ids:
            try:
                proof = self._evidence.prove(
                    transaction, session_token=command.session_token,
                    trace_id=command.trace_id, project_id=command.project_id,
                    evidence_id=evidence_id)
                if (type(proof) is not SectionEvidenceUseProof
                        or proof.project_id != command.project_id
                        or proof.evidence_id != evidence_id
                        or not _id(proof.document_id)
                        or not _id(proof.document_version_id)
                        or type(proof.observed_lock_version) is not int
                        or proof.observed_lock_version < 0
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32):
                    evidence = "UNAVAILABLE"
            except Exception:
                evidence = "UNAVAILABLE"
        return SectionVersionValidationFacts(
            integrity="PASS", content=content, requirements=requirements,
            evidence=evidence,
            trace=self._trace_status(transaction, command, version),
            spec=self._spec_status(transaction, version))

    def _spec_status(self, transaction: object,
                     version: SectionVersionHistoryView) -> str:
        if version.version_state != "DRAFT":
            return "UNAVAILABLE"
        refs = version.structured_spec_refs
        if version.spec_binding_state == "NONE_REQUIRED":
            return ("PASS" if not refs and is_normalized_spec_basis(
                version.spec_not_required_reason) else "UNAVAILABLE")
        if version.spec_binding_state != "FIXED_REFS" or self._specs is None:
            return "UNAVAILABLE"
        if (version.spec_not_required_reason is not None
                or type(refs) is not tuple or not 1 <= len(refs) <= 500
                or type(version.version_no) is not int or version.version_no < 2
                or not _id(version.supersedes_version_ref)
                or any(type(item) is not SectionStructuredSpecRef
                       or not _id(item.spec_series_id)
                       or not _id(item.structured_solution_spec_id)
                       or not is_normalized_spec_basis(item.fit_rationale)
                       for item in refs)
                or len({item.spec_series_id for item in refs}) != len(refs)
                or len({item.structured_solution_spec_id for item in refs}) != len(refs)):
            return "UNAVAILABLE"
        try:
            qualified = self._specs.prove(transaction, version=version)
            if type(qualified) is not tuple or len(qualified) != len(refs):
                return "UNAVAILABLE"
            requirements = {item.requirement_version_id
                            for item in version.requirement_refs}
            for ref, item in zip(refs, qualified, strict=True):
                if (type(item) is not QualifiedSectionStructuredSpec
                        or item.ref != ref
                        or type(item.spec_type) is not str or not item.spec_type
                        or type(item.content_fingerprint) is not bytes
                        or len(item.content_fingerprint) != 32
                        or not _id(item.review_id)
                        or not _id(item.review_round_id)
                        or not _id(item.source_section_version_id)
                        or type(item.source_content_fingerprint) is not bytes
                        or len(item.source_content_fingerprint) != 32
                        or type(item.shared_requirement_version_ids) is not tuple
                        or not item.shared_requirement_version_ids
                        or any(not _id(identifier) or identifier not in requirements
                               for identifier in item.shared_requirement_version_ids)):
                    return "UNAVAILABLE"
            return "PASS"
        except Exception:
            return "UNAVAILABLE"

    def _trace_status(self, transaction: object, command: ValidateSectionVersion,
                      version: SectionVersionHistoryView) -> str:
        if self._trace is None:
            return "UNAVAILABLE"
        try:
            target = TraceVersionRef(
                "solution", "SOL-05", version.solution_section_id,
                version.solution_section_version_id, "PROJECT", version.project_id)
            requirements = tuple(TraceVersionRef(
                "requirement", "REQ-03", ref.requirement_id,
                ref.requirement_version_id, "PROJECT", version.project_id)
                for ref in version.requirement_refs)
            proof = self._trace.prove(
                transaction,
                query=TraceProofQuery(command.session_token, command.trace_id),
                target=target, requirement_refs=requirements)
            if (type(proof) is not TraceImplementsCoverageProof
                    or proof.target != target
                    or proof.requirement_refs != requirements
                    or type(proof.trace_link_ids) is not tuple
                    or len(proof.trace_link_ids) != len(requirements)
                    or len(set(proof.trace_link_ids)) != len(requirements)
                    or any(not _id(link_id) for link_id in proof.trace_link_ids)):
                return "UNAVAILABLE"
            return "PASS"
        except TraceImplementsCoverageError as exc:
            return ("FAIL" if exc.code == "TRACE_COVERAGE_REQUIRED"
                    else "UNAVAILABLE")
        except Exception:
            return "UNAVAILABLE"


class SectionVersionValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 sections: SectionPort, versions: VersionPort,
                 current: SectionVersionCurrentValidator,
                 receipts: ReceiptPort, audit: AuditService,
                 audit_source: AuditSourcePort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(port is None for port in (
                unit_of_work, access, license_guard, authorization,
                sections, versions, current, receipts, audit, audit_source)):
            raise ValueError("SectionVersion validation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sections, self._versions = (
            authorization, sections, versions)
        self._current, self._receipts, self._audit = current, receipts, audit
        self._audit_source = audit_source
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(self, command: ValidateSectionVersion) -> SectionVersionValidationReport:
        if type(command) is not ValidateSectionVersion:
            raise SectionVersionValidationError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise SectionVersionValidationError()
                actor = self._access.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token,
                    now=now.astimezone(timezone.utc))
                if not _id(actor):
                    raise SectionVersionValidationError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SOL_SECTION_VERSION_VALIDATE")
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SOL_SECTION_VERSION_VALIDATE"):
                    raise SectionVersionValidationError("RESOURCE_NOT_FOUND")
                section = self._sections.get_current(
                    tx, project_id=command.project_id,
                    section_id=command.solution_section_id)
                if (type(section) is not SectionCurrentView
                        or section.project_id != command.project_id
                        or section.solution_section_id != command.solution_section_id
                        or section.section_state != "ACTIVE"):
                    raise SectionVersionValidationError("RESOURCE_NOT_FOUND")
                scope = command.scope(actor)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=command.request_fingerprint())
                version = self._versions.get(
                    tx, project_id=command.project_id,
                    section_id=command.solution_section_id,
                    version_id=command.solution_section_version_id)
                if (type(version) is not SectionVersionHistoryView
                        or version.project_id != command.project_id
                        or version.solution_section_id != command.solution_section_id
                        or version.solution_section_version_id != command.solution_section_version_id):
                    raise SectionVersionValidationError("RESOURCE_NOT_FOUND")
                fixed = SectionVersionValidationSnapshot(
                    version.project_id, version.solution_section_id,
                    version.solution_section_version_id, version.version_no,
                    version.version_state, version.content_fingerprint,
                    len(version.requirement_refs), len(version.evidence_ids))
                if previous is not None:
                    if previous.ref_type != OPERATION or previous.status_code != 200:
                        raise SectionVersionValidationError()
                    observation = self._audit_source.get(
                        tx, audit_event_id=previous.ref_id, actor_id=actor,
                        project_id=command.project_id,
                        section_id=command.solution_section_id,
                        version_id=command.solution_section_version_id)
                    if type(observation) is not SectionVersionValidationAudit:
                        raise SectionVersionValidationError()
                    facts = facts_from_audit_reason(observation.reason_code)
                    return build_section_version_validation_report(
                        replace(command, trace_id=observation.trace_id),
                        replace(fixed, version_state=observation.before_state),
                        facts, audit_event_id=observation.audit_event_id,
                        observed_at=observation.observed_at)
                facts = self._current.facts(tx, command=command, version=version)
                if type(facts) is not SectionVersionValidationFacts:
                    raise SectionVersionValidationError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action=AUDIT_ACTION, outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-05",
                    target_object_id=command.solution_section_id,
                    target_version_id=command.solution_section_version_id,
                    reason_code=audit_reason_for_facts(facts),
                    before_state=version.version_state,
                    after_state=version.version_state))
                if not _id(audit_id):
                    raise SectionVersionValidationError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    OPERATION, audit_id, 200))
                observation = self._audit_source.get(
                    tx, audit_event_id=audit_id, actor_id=actor,
                    project_id=command.project_id,
                    section_id=command.solution_section_id,
                    version_id=command.solution_section_version_id)
                if (type(observation) is not SectionVersionValidationAudit
                        or observation.trace_id != command.trace_id
                        or observation.reason_code != audit_reason_for_facts(facts)
                        or observation.before_state != version.version_state):
                    raise SectionVersionValidationError()
                report = build_section_version_validation_report(
                    command, fixed, facts, audit_event_id=audit_id,
                    observed_at=observation.observed_at)
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return report
        except SectionVersionValidationError:
            raise
        except ProjectAuthorizationError as error:
            raise SectionVersionValidationError(error.code) from None
        except RuntimeLicenseError:
            raise SectionVersionValidationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SectionVersionValidationError(error.code) from None
        except Exception:
            raise SectionVersionValidationError() from None
