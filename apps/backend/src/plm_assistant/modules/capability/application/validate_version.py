"""Idempotent current-source validation report for one immutable Version."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)

from .create_version import CapabilityItemDraft
from .source_validation import CapabilitySourceValidationError, CapabilitySourceValidator


_REASONS = {
    (): "VALIDATION_PASSED",
    ("SOURCE_UNAVAILABLE",): "SOURCE_UNAVAILABLE",
    ("EVIDENCE_UNAVAILABLE",): "EVIDENCE_UNAVAILABLE",
    ("SOURCE_UNAVAILABLE", "EVIDENCE_UNAVAILABLE"): "SOURCE_AND_EVIDENCE_UNAVAILABLE",
}
_ISSUES = {value: key for key, value in _REASONS.items()}


class CapabilityVersionValidationError(RuntimeError):
    def __init__(self, code: str = "CAPABILITY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidateCapabilityVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    baseline_id: uuid.UUID
    baseline_version_id: uuid.UUID
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CapabilityVersionSnapshot:
    baseline_id: uuid.UUID
    baseline_version_id: uuid.UUID
    version_no: int
    version_state: str
    source_collection_ref: str
    content_fingerprint: bytes = field(repr=False)
    items: tuple[CapabilityItemDraft, ...]


@dataclass(frozen=True, slots=True)
class CapabilityValidationAudit:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    observed_at: datetime
    reason_code: str


@dataclass(frozen=True, slots=True)
class CapabilityVersionValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    baseline_id: uuid.UUID
    baseline_version_id: uuid.UUID
    version_no: int
    version_state: str
    source_collection_ref: str
    content_fingerprint: bytes = field(repr=False)
    item_count: int
    document_ref_count: int
    evidence_ref_count: int
    valid: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime


class CapabilityValidationAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class CapabilityValidationLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class CapabilityValidationRepositoryPort(Protocol):
    def lock_snapshot(self, transaction: object, *, baseline_id: uuid.UUID,
                      baseline_version_id: uuid.UUID) -> CapabilityVersionSnapshot | None: ...


class CapabilityValidationEvidencePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class CapabilityValidationAuditPort(Protocol):
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID,
            baseline_version_id: uuid.UUID) -> CapabilityValidationAudit | None: ...


class CapabilityValidationReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class CapabilityVersionValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: CapabilityValidationAccessPort,
                 license_guard: CapabilityValidationLicensePort,
                 sources: CapabilitySourceValidator,
                 evidence: CapabilityValidationEvidencePort,
                 repository: CapabilityValidationRepositoryPort,
                 audit_source: CapabilityValidationAuditPort,
                 receipts: CapabilityValidationReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (
                unit_of_work, access, license_guard, sources, evidence,
                repository, audit_source, receipts, audit)):
            raise ValueError("Capability validation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._sources, self._evidence, self._repo = sources, evidence, repository
        self._audit_source, self._receipts, self._audit = audit_source, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(self, command: ValidateCapabilityVersion) -> CapabilityVersionValidationReport:
        if (type(command) is not ValidateCapabilityVersion
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.baseline_id, command.baseline_version_id))):
            raise CapabilityVersionValidationError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "baseline_id": str(command.baseline_id),
                "baseline_version_id": str(command.baseline_version_id),
            })
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None,
                    operation="V1_CAP_VERSION_VALIDATE", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                snapshot = self._repo.lock_snapshot(
                    tx, baseline_id=command.baseline_id,
                    baseline_version_id=command.baseline_version_id,
                )
                if type(snapshot) is not CapabilityVersionSnapshot:
                    raise CapabilityVersionValidationError("CAPABILITY_NOT_FOUND")
                if replay is not None:
                    if replay.ref_type != "V1_CAP_VERSION_VALIDATION" or replay.status_code != 200:
                        raise CapabilityVersionValidationError()
                    proof = self._audit_source.get(
                        tx, audit_event_id=replay.ref_id, actor_id=actor,
                        baseline_version_id=command.baseline_version_id,
                    )
                    if type(proof) is not CapabilityValidationAudit:
                        raise CapabilityVersionValidationError()
                    return self._report(snapshot, proof)
                issues = self._current_issues(tx, snapshot)
                reason = _REASONS[issues]
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="CAP_VERSION_VALIDATED", outcome="SUCCESS",
                    target_owner_module="capability", target_object_type="CAP-02",
                    target_object_id=command.baseline_version_id,
                    target_version_id=command.baseline_version_id,
                    reason_code=reason, before_state=snapshot.version_state,
                    after_state=snapshot.version_state,
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_CAP_VERSION_VALIDATION", audit_id, 200,
                ))
                proof = self._audit_source.get(
                    tx, audit_event_id=audit_id, actor_id=actor,
                    baseline_version_id=command.baseline_version_id,
                )
                if type(proof) is not CapabilityValidationAudit:
                    raise CapabilityVersionValidationError()
                tx.commit()
                return self._report(snapshot, proof)
        except CapabilityVersionValidationError:
            raise
        except RuntimeLicenseError:
            raise CapabilityVersionValidationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise CapabilityVersionValidationError(error.code) from None
        except Exception:
            raise CapabilityVersionValidationError() from None

    def _current_issues(self, tx: object,
                        snapshot: CapabilityVersionSnapshot) -> tuple[str, ...]:
        issues: list[str] = []
        documents = self._unique_documents(snapshot.items)
        try:
            source = self._sources.validate(tx, documents)
            if source.source_collection_ref != snapshot.source_collection_ref:
                issues.append("SOURCE_UNAVAILABLE")
        except CapabilitySourceValidationError:
            issues.append("SOURCE_UNAVAILABLE")
        evidence_invalid = False
        for item in snapshot.items:
            pairs = {(ref.document_id, ref.document_version_id) for ref in item.document_refs}
            for evidence_id in item.evidence_refs:
                source = self._evidence.get_for_trace(
                    tx, scope="GLOBAL", project_id=None, evidence_id=evidence_id,
                )
                if (type(source) is not LockedEvidenceSource
                        or (source.document_id, source.document_version_id) not in pairs):
                    evidence_invalid = True
        if evidence_invalid:
            issues.append("EVIDENCE_UNAVAILABLE")
        return tuple(issues)

    @staticmethod
    def _unique_documents(items: tuple[CapabilityItemDraft, ...]):
        found = {ref.document_version_id: ref for item in items for ref in item.document_refs}
        return tuple(sorted(found.values(), key=lambda ref: str(ref.document_version_id)))

    @staticmethod
    def _report(snapshot: CapabilityVersionSnapshot,
                proof: CapabilityValidationAudit) -> CapabilityVersionValidationReport:
        issues = _ISSUES.get(proof.reason_code)
        if issues is None:
            raise CapabilityVersionValidationError()
        return CapabilityVersionValidationReport(
            proof.audit_event_id, proof.trace_id, snapshot.baseline_id,
            snapshot.baseline_version_id, snapshot.version_no,
            snapshot.version_state, snapshot.source_collection_ref,
            snapshot.content_fingerprint, len(snapshot.items),
            sum(len(item.document_refs) for item in snapshot.items),
            sum(len(item.evidence_refs) for item in snapshot.items),
            not issues, issues, proof.observed_at,
        )

    def _require_admin(self, tx: object,
                       command: ValidateCapabilityVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise CapabilityVersionValidationError()
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise CapabilityVersionValidationError("AUTH_ACCESS_DENIED")
        return actor
