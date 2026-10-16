"""Human Evidence first decision with live source proof and atomic receipt/audit."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts, DocumentReadError, DocumentReadQuery,
)
from plm_assistant.modules.evidence.application.eligibility_access import (
    EvidenceEligibilityAccessError,
)
from plm_assistant.modules.evidence.application.eligibility_record import LockedEvidenceEligibility
from plm_assistant.modules.evidence.domain.eligibility import (
    EvidenceEligibilityError, decide_eligibility,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)


class EvidenceEligibilityCommandError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SetEvidenceEligibility:
    actor_id: uuid.UUID
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    evidence_id: uuid.UUID
    expected_version: int
    requested_state: str
    reason: str


@dataclass(frozen=True, slots=True)
class SetEvidenceEligibilityResult:
    evidence_id: uuid.UUID
    eligibility_state: str
    eligibility_reason: str
    etag: str


class EvidenceEligibilityAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               operation: str, session_token: bytes,
                               csrf_token: bytes) -> None: ...


class EvidenceSourceFactsPort(Protocol):
    def get_source_facts_for_evidence(
            self, transaction: object, query: DocumentReadQuery,
            document_id: uuid.UUID,
            document_version_id: uuid.UUID) -> DocumentEvidenceSourceFacts: ...


class EvidenceEligibilityRepositoryPort(Protocol):
    def lock(self, transaction: object, *, scope: str,
             project_id: uuid.UUID | None,
             evidence_id: uuid.UUID) -> LockedEvidenceEligibility | None: ...
    def decide(self, transaction: object, *, locked: LockedEvidenceEligibility,
               state: str, reason: str, actor_id: uuid.UUID) -> int | None: ...


class EvidenceEligibilityReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class EvidenceEligibilityLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class EvidenceEligibilityService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: EvidenceEligibilityAccessPort,
                 source_facts: EvidenceSourceFactsPort,
                 repository: EvidenceEligibilityRepositoryPort,
                 receipts: EvidenceEligibilityReceiptPort,
                 license_guard: EvidenceEligibilityLicensePort,
                 audit: AuditService) -> None:
        if any(item is None for item in (
                unit_of_work, access, source_facts, repository, receipts,
                license_guard, audit)):
            raise ValueError("Evidence eligibility dependencies required")
        self._uow, self._access, self._source = unit_of_work, access, source_facts
        self._repository, self._receipts = repository, receipts
        self._guard, self._audit = license_guard, audit

    def set(self, command: SetEvidenceEligibility, *,
            idempotency_key: str) -> SetEvidenceEligibilityResult:
        self._validate(command)
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "scope": command.scope,
                "project_id": str(command.project_id) if command.project_id else None,
                "evidence_id": str(command.evidence_id),
                "expected_version": command.expected_version,
                "requested_state": command.requested_state,
                "reason": command.reason,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                self._access.require_in_transaction(
                    tx, actor_id=command.actor_id, scope=command.scope,
                    project_id=command.project_id,
                    operation="V1_EVIDENCE_SET_ELIGIBILITY",
                    session_token=command.session_token,
                    csrf_token=command.csrf_token,
                )
                locked = self._repository.lock(
                    tx, scope=command.scope, project_id=command.project_id,
                    evidence_id=command.evidence_id,
                )
                if (type(locked) is not LockedEvidenceEligibility
                        or locked.evidence_id != command.evidence_id
                        or locked.scope != command.scope
                        or locked.project_id != command.project_id
                        or type(locked.document_id) is not uuid.UUID
                        or locked.document_id.int == 0
                        or type(locked.document_version_id) is not uuid.UUID
                        or locked.document_version_id.int == 0
                        or type(locked.lock_version) is not int
                        or locked.lock_version < 0):
                    raise EvidenceEligibilityCommandError("RESOURCE_NOT_FOUND")
                query = DocumentReadQuery(command.session_token, command.trace_id,
                                          command.scope, command.project_id)
                source = self._source.get_source_facts_for_evidence(
                    tx, query, locked.document_id, locked.document_version_id,
                )
                if (type(source) is not DocumentEvidenceSourceFacts
                        or source.document_id != locked.document_id
                        or source.document_version_id != locked.document_version_id
                        or source.scope != locked.scope
                        or source.project_id != locked.project_id
                        or source.document_state not in ("ACTIVE", "ARCHIVED")):
                    raise EvidenceEligibilityCommandError("RESOURCE_NOT_FOUND")
                if source.document_category == "TEMPLATE" and command.requested_state == "ELIGIBLE":
                    raise EvidenceEligibilityCommandError("CONFLICT_STATE")
                receipt_scope = IdempotencyScope.from_key(
                    actor_id=command.actor_id, project_id=command.project_id,
                    operation="V1_EVIDENCE_SET_ELIGIBILITY", key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=receipt_scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if (replay.ref_type != "V1_EVIDENCE_ELIGIBILITY"
                            or replay.ref_id != command.evidence_id
                            or replay.status_code != 200
                            or locked.eligibility_state != command.requested_state
                            or locked.eligibility_reason != command.reason
                            or locked.lock_version != command.expected_version + 1):
                        raise EvidenceEligibilityCommandError("CONFLICT_STATE")
                    return self._result(command, locked.lock_version)
                if locked.lock_version != command.expected_version:
                    raise EvidenceEligibilityCommandError("CONFLICT_VERSION")
                try:
                    decision = decide_eligibility(
                        current_state=locked.eligibility_state,
                        requested_state=command.requested_state, reason=command.reason,
                        document_category=source.document_category,
                    )
                except EvidenceEligibilityError as error:
                    raise EvidenceEligibilityCommandError(
                        "CONFLICT_STATE" if error.code in (
                            "EVIDENCE_STATE_CONFLICT", "EVIDENCE_TEMPLATE_NOT_ELIGIBLE")
                        else "VALIDATION_FAILED") from None
                new_version = self._repository.decide(
                    tx, locked=locked, state=decision.state,
                    reason=decision.reason, actor_id=command.actor_id,
                )
                if type(new_version) is not int or new_version != command.expected_version + 1:
                    raise EvidenceEligibilityCommandError("CONFLICT_VERSION")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope="DEPLOYMENT" if command.scope == "GLOBAL" else "PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=command.actor_id, original_actor_id=None,
                    actor_hint_digest=None, action="EVIDENCE_ELIGIBILITY_SET",
                    outcome="SUCCESS", target_owner_module="evidence",
                    target_object_type="EVD-01", target_object_id=command.evidence_id,
                    before_state="CANDIDATE", after_state=decision.state,
                ))
                self._receipts.complete(
                    tx, scope=receipt_scope,
                    result=IdempotencyResult(
                        "V1_EVIDENCE_ELIGIBILITY", command.evidence_id, 200),
                )
                tx.commit()
                return self._result(command, new_version)
        except RuntimeLicenseError:
            raise EvidenceEligibilityCommandError("LICENSE_OPERATION_DENIED") from None
        except (IdempotencyError, EvidenceEligibilityAccessError,
                DocumentReadError) as error:
            code = getattr(error, "code", "SYSTEM_UNAVAILABLE")
            if code == "DOCUMENT_UNAVAILABLE":
                code = "SYSTEM_UNAVAILABLE"
            raise EvidenceEligibilityCommandError(code) from None

    @staticmethod
    def _validate(command: SetEvidenceEligibility) -> None:
        if (type(command) is not SetEvidenceEligibility
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.actor_id, command.trace_id, command.evidence_id))
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or command.scope not in ("GLOBAL", "PROJECT")
                or command.scope == "GLOBAL" and command.project_id is not None
                or command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0)
                or type(command.expected_version) is not int
                or not 0 <= command.expected_version < 2**63 - 1
                or command.requested_state not in ("ELIGIBLE", "INELIGIBLE")
                or type(command.reason) is not str
                or not 1 <= len(command.reason) <= 1024
                or command.reason != command.reason.strip()
                or any(ord(char) < 32 for char in command.reason)):
            raise EvidenceEligibilityCommandError("VALIDATION_FAILED")

    @staticmethod
    def _result(command: SetEvidenceEligibility,
                version: int) -> SetEvidenceEligibilityResult:
        return SetEvidenceEligibilityResult(
            command.evidence_id, command.requested_state,
            command.reason, f'"v{version}"',
        )
