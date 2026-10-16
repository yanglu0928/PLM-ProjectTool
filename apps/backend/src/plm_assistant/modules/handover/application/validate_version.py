"""Idempotent current-input validation for an immutable Handover Version."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.task_read import AITaskView
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.capability.application.read_capability import CapabilityItemView, CapabilityVersionView
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationError, ProjectAuthorizationService

from .create_version import (
    HandoverAnalysisItemDraft, HandoverCapabilityPort, HandoverAITaskPort,
    HandoverEvidencePort, HandoverVersionCreateService,
)
from .source_validation import HandoverDocumentRef, HandoverSourceValidationError, HandoverSourceValidator


_ORDER = (
    "CONTENT_FINGERPRINT_MISMATCH", "SOURCE_UNAVAILABLE", "EVIDENCE_UNAVAILABLE",
    "CAPABILITY_UNAVAILABLE", "AI_PROVENANCE_UNAVAILABLE",
    "INPUT_GUIDANCE_INCOMPLETE", "ACTION_ITEM_REQUIRED",
)
_LETTERS = dict(zip(_ORDER, "FSECAGT", strict=True))
_BY_LETTER = {value: key for key, value in _LETTERS.items()}
_OPERATION = "V1_HND_VERSION_VALIDATE"


class HandoverVersionValidationError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidateHandoverVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class HandoverVersionSnapshot:
    handover_analysis_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    source_set_ref: str
    capability_baseline_id: uuid.UUID
    capability_baseline_version_ref: uuid.UUID
    content_fingerprint: bytes = field(repr=False)
    source_documents: tuple[HandoverDocumentRef, ...]
    items: tuple[HandoverAnalysisItemDraft, ...]
    ai_task_refs: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class HandoverValidationAudit:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    observed_at: datetime
    reason_code: str


@dataclass(frozen=True, slots=True)
class HandoverVersionValidationReport:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    item_count: int
    source_count: int
    evidence_count: int
    capability_ref_count: int
    ai_task_count: int
    valid: bool
    issue_codes: tuple[str, ...]
    observed_at: datetime


class HandoverValidationAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class HandoverValidationLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class HandoverValidationRepositoryPort(Protocol):
    def lock_snapshot(self, transaction: object, *, project_id: uuid.UUID,
                      handover_analysis_id: uuid.UUID,
                      handover_analysis_version_id: uuid.UUID
                      ) -> HandoverVersionSnapshot | None: ...


class HandoverValidationAuditPort(Protocol):
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID,
            handover_analysis_version_id: uuid.UUID) -> HandoverValidationAudit | None: ...


class HandoverValidationReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class HandoverVersionValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: HandoverValidationAccessPort,
                 license_guard: HandoverValidationLicensePort,
                 authorization: ProjectAuthorizationService,
                 sources: HandoverSourceValidator,
                 evidence: HandoverEvidencePort,
                 capabilities: HandoverCapabilityPort,
                 ai_tasks: HandoverAITaskPort,
                 repository: HandoverValidationRepositoryPort,
                 audit_source: HandoverValidationAuditPort,
                 receipts: HandoverValidationReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        dependencies = (unit_of_work, access, license_guard, authorization, sources,
                        evidence, capabilities, ai_tasks, repository,
                        audit_source, receipts, audit)
        if any(value is None for value in dependencies):
            raise ValueError("Handover validation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sources, self._evidence = authorization, sources, evidence
        self._capabilities, self._ai_tasks, self._repository = capabilities, ai_tasks, repository
        self._audit_source, self._receipts, self._audit = audit_source, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(self, command: ValidateHandoverVersion) -> HandoverVersionValidationReport:
        if (type(command) is not ValidateHandoverVersion
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.handover_analysis_id,
                    command.handover_analysis_version_id))):
            raise HandoverVersionValidationError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "handover_analysis_id": str(command.handover_analysis_id),
                "handover_analysis_version_id": str(command.handover_analysis_version_id),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="HND_VERSION_VALIDATE",
                )
                if authorized.user_id != actor or authorized.project_id != command.project_id:
                    raise HandoverVersionValidationError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
                snapshot = self._repository.lock_snapshot(
                    tx, project_id=command.project_id,
                    handover_analysis_id=command.handover_analysis_id,
                    handover_analysis_version_id=command.handover_analysis_version_id,
                )
                if type(snapshot) is not HandoverVersionSnapshot:
                    raise HandoverVersionValidationError("RESOURCE_NOT_FOUND")
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise HandoverVersionValidationError()
                    proof = self._audit_source.get(
                        tx, audit_event_id=replay.ref_id, actor_id=actor,
                        project_id=command.project_id,
                        handover_analysis_version_id=command.handover_analysis_version_id,
                    )
                    if type(proof) is not HandoverValidationAudit:
                        raise HandoverVersionValidationError()
                    return self._report(snapshot, proof)
                issues = self._current_issues(tx, snapshot)
                reason = self._reason(issues)
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="HND_VERSION_VALIDATED", outcome="SUCCESS",
                    target_owner_module="handover", target_object_type="HND-02",
                    target_object_id=command.handover_analysis_version_id,
                    target_version_id=command.handover_analysis_version_id,
                    reason_code=reason, before_state=snapshot.version_state,
                    after_state=snapshot.version_state,
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, audit_id, 200,
                ))
                proof = self._audit_source.get(
                    tx, audit_event_id=audit_id, actor_id=actor,
                    project_id=command.project_id,
                    handover_analysis_version_id=command.handover_analysis_version_id,
                )
                if type(proof) is not HandoverValidationAudit:
                    raise HandoverVersionValidationError()
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return self._report(snapshot, proof)
        except HandoverVersionValidationError:
            raise
        except ProjectAuthorizationError as error:
            raise HandoverVersionValidationError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverVersionValidationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise HandoverVersionValidationError(error.code) from None
        except Exception:
            raise HandoverVersionValidationError() from None

    def _current_issues(self, tx: object, snapshot: HandoverVersionSnapshot) -> tuple[str, ...]:
        found: set[str] = set()
        payload = self._snapshot_payload(snapshot)
        if not hmac.compare_digest(canonical_payload_fingerprint(payload), snapshot.content_fingerprint):
            found.add("CONTENT_FINGERPRINT_MISMATCH")
        try:
            fixed = self._sources.validate(
                tx, project_id=snapshot.project_id, references=snapshot.source_documents,
            )
            if fixed.source_set_ref != snapshot.source_set_ref:
                found.add("SOURCE_UNAVAILABLE")
        except HandoverSourceValidationError:
            found.add("SOURCE_UNAVAILABLE")
        source_pairs = {(ref.document_id, ref.document_version_id)
                        for ref in snapshot.source_documents}
        for item in snapshot.items:
            if item.source_missing:
                found.add("ACTION_ITEM_REQUIRED")
            for evidence_id in item.evidence_refs:
                evidence = self._evidence.get_for_trace(
                    tx, scope="PROJECT", project_id=snapshot.project_id,
                    evidence_id=evidence_id,
                )
                if (type(evidence) is not LockedEvidenceSource
                        or (evidence.document_id, evidence.document_version_id) not in source_pairs):
                    found.add("EVIDENCE_UNAVAILABLE")
        version = self._capabilities.get_version(
            tx, visibility="CURRENT_APPROVED", baseline_id=snapshot.capability_baseline_id,
            baseline_version_id=snapshot.capability_baseline_version_ref,
        )
        capability_items: tuple[CapabilityItemView, ...] = ()
        if type(version) is CapabilityVersionView and version.state == "APPROVED":
            capability_items = self._capabilities.list_items(
                tx, visibility="CURRENT_APPROVED", baseline_id=snapshot.capability_baseline_id,
                baseline_version_id=snapshot.capability_baseline_version_ref,
                after_ordinal=None, limit=501,
            )
        allowed = {item.capability_item_id for item in capability_items
                   if item.state == "AVAILABLE"}
        if (type(version) is not CapabilityVersionView
                or len(capability_items) != version.declared_item_count
                or any(ref.capability_item_id not in allowed
                       for item in snapshot.items for ref in item.capability_refs)):
            found.add("CAPABILITY_UNAVAILABLE")
        for task_id in snapshot.ai_task_refs:
            task = self._ai_tasks.get(tx, ai_task_id=task_id, project_id=snapshot.project_id)
            if (type(task) is not AITaskView or task.task_type != "GAP_ANALYSIS"
                    or task.task_state != "SUCCEEDED"):
                found.add("AI_PROVENANCE_UNAVAILABLE")
        try:
            stable: set[uuid.UUID] = set()
            for item in snapshot.items:
                HandoverVersionCreateService._validate_item(item, stable)
                stable.add(item.analysis_item_id)
        except Exception:
            found.add("INPUT_GUIDANCE_INCOMPLETE")
        return tuple(code for code in _ORDER if code in found)

    @staticmethod
    def _snapshot_payload(snapshot: HandoverVersionSnapshot) -> dict[str, object]:
        sources = sorted(
            snapshot.source_documents, key=lambda ref: str(ref.document_version_id),
        )
        return {
            "project_id": str(snapshot.project_id),
            "handover_analysis_id": str(snapshot.handover_analysis_id),
            "source_documents": [{"document_id": str(ref.document_id),
                                  "document_version_id": str(ref.document_version_id)}
                                 for ref in sources],
            "capability_baseline_id": str(snapshot.capability_baseline_id),
            "capability_baseline_version_id": str(
                snapshot.capability_baseline_version_ref
            ),
            "items": [HandoverVersionCreateService._item_payload(item)
                      for item in snapshot.items],
            "ai_task_refs": sorted(str(ref) for ref in snapshot.ai_task_refs),
        }

    @staticmethod
    def _reason(issues: tuple[str, ...]) -> str:
        return ("HND_VALIDATION_PASSED" if not issues else
                "HND_VALIDATION_FAILED_" + "".join(_LETTERS[issue] for issue in issues))

    @staticmethod
    def _issues(reason: str) -> tuple[str, ...]:
        if reason == "HND_VALIDATION_PASSED":
            return ()
        prefix = "HND_VALIDATION_FAILED_"
        if not reason.startswith(prefix):
            raise HandoverVersionValidationError()
        try:
            issues = tuple(_BY_LETTER[letter] for letter in reason[len(prefix):])
        except KeyError:
            raise HandoverVersionValidationError() from None
        if tuple(code for code in _ORDER if code in issues) != issues:
            raise HandoverVersionValidationError()
        return issues

    @staticmethod
    def _report(snapshot: HandoverVersionSnapshot,
                proof: HandoverValidationAudit) -> HandoverVersionValidationReport:
        issues = HandoverVersionValidationService._issues(proof.reason_code)
        return HandoverVersionValidationReport(
            proof.audit_event_id, proof.trace_id, snapshot.handover_analysis_id,
            snapshot.handover_analysis_version_id, snapshot.project_id,
            snapshot.version_no, snapshot.version_state, len(snapshot.items),
            len(snapshot.source_documents),
            sum(len(item.evidence_refs) for item in snapshot.items),
            sum(len(item.capability_refs) for item in snapshot.items),
            len(snapshot.ai_task_refs), not issues, issues, proof.observed_at,
        )

    def _actor(self, tx: object, command: ValidateHandoverVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HandoverVersionValidationError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise HandoverVersionValidationError("AUTH_ACCESS_DENIED")
        return actor
