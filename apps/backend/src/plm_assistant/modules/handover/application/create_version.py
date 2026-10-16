"""Atomic immutable DRAFT HandoverAnalysisVersion creation."""

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
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityItemView, CapabilityVersionView,
)
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .source_validation import (
    HandoverDocumentRef, HandoverSourceValidationError, HandoverSourceValidator,
)


_TYPES = frozenset({"GAP", "MISSING", "CONFLICT", "RISK", "SCOPE", "NEED_CONFIRM"})
_SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
_PRIORITIES = frozenset({"LOW", "MEDIUM", "HIGH", "URGENT"})
_OPERATION = "V1_HND_VERSION_CREATE"


class HandoverVersionCreateError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class HandoverCapabilityItemRef:
    capability_item_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class HandoverItemOptionDraft:
    option_code: str
    label: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class HandoverAnalysisItemDraft:
    analysis_item_id: uuid.UUID
    item_type: str
    title: str
    statement: str
    impact: str
    severity: str
    priority: str
    recommendation: str | None
    confirmation_question: str | None
    required_input_spec: dict[str, object]
    source_missing: bool
    evidence_refs: tuple[uuid.UUID, ...]
    capability_refs: tuple[HandoverCapabilityItemRef, ...]
    options: tuple[HandoverItemOptionDraft, ...]


@dataclass(frozen=True, slots=True)
class CreateHandoverVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    expected_lock_version: int
    source_documents: tuple[HandoverDocumentRef, ...]
    capability_baseline_id: uuid.UUID
    capability_baseline_version_id: uuid.UUID
    items: tuple[HandoverAnalysisItemDraft, ...]
    ai_task_refs: tuple[uuid.UUID, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class HandoverAnalysisLock:
    handover_analysis_id: uuid.UUID
    project_id: uuid.UUID
    analysis_state: str
    source_set_ref: str
    lock_version: int
    highest_version_no: int
    latest_version_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class CreatedHandoverVersion:
    handover_analysis_version_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    source_set_ref: str
    capability_baseline_id: uuid.UUID
    capability_baseline_version_ref: uuid.UUID
    content_fingerprint: bytes = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    expected_lock_version: int
    lock_version: int

    def __post_init__(self) -> None:
        required = (
            self.handover_analysis_version_id, self.handover_analysis_id,
            self.project_id, self.capability_baseline_id,
            self.capability_baseline_version_ref, self.created_by,
        )
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in required)
                or self.version_no < 1 or self.version_state != "DRAFT"
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or self.lock_version != self.expected_lock_version + 1
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None):
            raise HandoverVersionCreateError()


class HandoverVersionAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class HandoverVersionLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class HandoverEvidencePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class HandoverCapabilityPort(Protocol):
    def get_version(self, transaction: object, *, visibility: str,
                    baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> CapabilityVersionView | None: ...
    def list_items(self, transaction: object, *, visibility: str,
                   baseline_id: uuid.UUID, baseline_version_id: uuid.UUID,
                   after_ordinal: int | None,
                   limit: int) -> tuple[CapabilityItemView, ...]: ...


class HandoverAITaskPort(Protocol):
    def get(self, transaction: object, *, ai_task_id: uuid.UUID,
            project_id: uuid.UUID) -> AITaskView | None: ...


class HandoverVersionRepositoryPort(Protocol):
    def lock_analysis(self, transaction: object, *, project_id: uuid.UUID,
                      handover_analysis_id: uuid.UUID) -> HandoverAnalysisLock | None: ...
    def create(self, transaction: object, *, analysis: HandoverAnalysisLock,
               handover_analysis_version_id: uuid.UUID,
               capability_baseline_id: uuid.UUID,
               capability_baseline_version_id: uuid.UUID,
               source_documents: tuple[HandoverDocumentRef, ...],
               items: tuple[HandoverAnalysisItemDraft, ...],
               ai_task_refs: tuple[uuid.UUID, ...], content_fingerprint: bytes,
               actor_id: uuid.UUID) -> CreatedHandoverVersion: ...
    def initial_view(self, transaction: object, *,
                     handover_analysis_version_id: uuid.UUID,
                     handover_analysis_id: uuid.UUID, project_id: uuid.UUID,
                     actor_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedHandoverVersion | None: ...


class HandoverVersionReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class HandoverVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: HandoverVersionAccessPort,
                 license_guard: HandoverVersionLicensePort,
                 authorization: ProjectAuthorizationService,
                 sources: HandoverSourceValidator,
                 evidence: HandoverEvidencePort,
                 capabilities: HandoverCapabilityPort,
                 ai_tasks: HandoverAITaskPort,
                 repository: HandoverVersionRepositoryPort,
                 receipts: HandoverVersionReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        dependencies = (unit_of_work, access, license_guard, authorization, sources,
                        evidence, capabilities, ai_tasks, repository, receipts, audit)
        if any(item is None for item in dependencies):
            raise ValueError("HandoverVersion dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sources, self._evidence = authorization, sources, evidence
        self._capabilities, self._ai_tasks = capabilities, ai_tasks
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateHandoverVersion) -> CreatedHandoverVersion:
        payload = self._validate_and_payload(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            content_fingerprint = canonical_payload_fingerprint(payload)
            request_fingerprint = canonical_payload_fingerprint({
                "content_fingerprint": content_fingerprint.hex(),
                "expected_lock_version": command.expected_lock_version,
            })
            version_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="HND_VERSION_CREATE",
                )
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "HND_VERSION_CREATE"):
                    raise HandoverVersionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise HandoverVersionCreateError()
                    result = self._repository.initial_view(
                        tx, handover_analysis_version_id=replay.ref_id,
                        handover_analysis_id=command.handover_analysis_id,
                        project_id=command.project_id, actor_id=actor,
                        expected_lock_version=command.expected_lock_version,
                    )
                    if (type(result) is not CreatedHandoverVersion
                            or not hmac.compare_digest(
                                result.content_fingerprint, content_fingerprint)):
                        raise HandoverVersionCreateError()
                    return result
                analysis = self._repository.lock_analysis(
                    tx, project_id=command.project_id,
                    handover_analysis_id=command.handover_analysis_id,
                )
                if type(analysis) is not HandoverAnalysisLock:
                    raise HandoverVersionCreateError("RESOURCE_NOT_FOUND")
                if analysis.analysis_state != "ACTIVE":
                    raise HandoverVersionCreateError("HANDOVER_STATE_CONFLICT")
                if analysis.lock_version != command.expected_lock_version:
                    raise HandoverVersionCreateError("CONFLICT_VERSION")
                validated_sources = self._sources.validate(
                    tx, project_id=command.project_id,
                    references=command.source_documents,
                )
                if not hmac.compare_digest(
                        validated_sources.source_set_ref, analysis.source_set_ref):
                    raise HandoverVersionCreateError("HANDOVER_SOURCE_CONFLICT")
                allowed_capabilities = self._validate_capability(tx, command)
                self._validate_evidence(tx, command)
                self._validate_capability_refs(command.items, allowed_capabilities)
                self._validate_ai_tasks(tx, command)
                result = self._repository.create(
                    tx, analysis=analysis,
                    handover_analysis_version_id=version_id,
                    capability_baseline_id=command.capability_baseline_id,
                    capability_baseline_version_id=command.capability_baseline_version_id,
                    source_documents=validated_sources.documents,
                    items=command.items, ai_task_refs=command.ai_task_refs,
                    content_fingerprint=content_fingerprint, actor_id=actor,
                )
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="HND_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="handover", target_object_type="HND-02",
                    target_object_id=version_id, target_version_id=version_id,
                    after_state="DRAFT",
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise HandoverVersionCreateError()
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, version_id, 201),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except HandoverVersionCreateError:
            raise
        except HandoverSourceValidationError:
            raise HandoverVersionCreateError("HANDOVER_SOURCE_UNAVAILABLE") from None
        except ProjectAuthorizationError as error:
            raise HandoverVersionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise HandoverVersionCreateError(error.code) from None
        except Exception:
            raise HandoverVersionCreateError() from None

    @staticmethod
    def _validate_and_payload(command: CreateHandoverVersion) -> dict[str, object]:
        if type(command) is not CreateHandoverVersion:
            raise HandoverVersionCreateError("VALIDATION_FAILED")
        ids = (command.project_id, command.handover_analysis_id,
               command.capability_baseline_id, command.capability_baseline_version_id)
        if (type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or any(type(value) is not uuid.UUID or value.int == 0 for value in ids)
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775806
                or type(command.source_documents) is not tuple
                or not 1 <= len(command.source_documents) <= 500
                or any(type(ref) is not HandoverDocumentRef
                       for ref in command.source_documents)
                or len({ref.document_id for ref in command.source_documents})
                   != len(command.source_documents)
                or len({ref.document_version_id for ref in command.source_documents})
                   != len(command.source_documents)
                or type(command.items) is not tuple or not 1 <= len(command.items) <= 500
                or any(type(item) is not HandoverAnalysisItemDraft for item in command.items)
                or type(command.ai_task_refs) is not tuple or len(command.ai_task_refs) > 100
                or any(type(ref) is not uuid.UUID or ref.int == 0
                       for ref in command.ai_task_refs)
                or len(set(command.ai_task_refs)) != len(command.ai_task_refs)):
            raise HandoverVersionCreateError("VALIDATION_FAILED")
        stable: set[uuid.UUID] = set()
        payload_items: list[dict[str, object]] = []
        for item in command.items:
            HandoverVersionCreateService._validate_item(item, stable)
            stable.add(item.analysis_item_id)
            payload_items.append(HandoverVersionCreateService._item_payload(item))
        sources = sorted(command.source_documents, key=lambda ref: str(ref.document_version_id))
        return {
            "project_id": str(command.project_id),
            "handover_analysis_id": str(command.handover_analysis_id),
            "source_documents": [{"document_id": str(ref.document_id),
                                  "document_version_id": str(ref.document_version_id)}
                                 for ref in sources],
            "capability_baseline_id": str(command.capability_baseline_id),
            "capability_baseline_version_id": str(command.capability_baseline_version_id),
            "items": payload_items,
            "ai_task_refs": sorted(str(ref) for ref in command.ai_task_refs),
        }

    @staticmethod
    def _validate_item(item: HandoverAnalysisItemDraft,
                       stable: set[uuid.UUID]) -> None:
        def text(value: object, maximum: int) -> bool:
            return type(value) is str and 1 <= len(value) <= maximum and value == value.strip()
        if (type(item.analysis_item_id) is not uuid.UUID or item.analysis_item_id.int == 0
                or item.analysis_item_id in stable or item.item_type not in _TYPES
                or not text(item.title, 255) or not text(item.statement, 4000)
                or not text(item.impact, 2000) or item.severity not in _SEVERITIES
                or item.priority not in _PRIORITIES
                or item.recommendation is not None and not text(item.recommendation, 2000)
                or item.confirmation_question is not None
                   and not text(item.confirmation_question, 2000)
                or type(item.required_input_spec) is not dict
                or type(item.source_missing) is not bool
                or type(item.evidence_refs) is not tuple or len(item.evidence_refs) > 200
                or any(type(ref) is not uuid.UUID or ref.int == 0 for ref in item.evidence_refs)
                or len(set(item.evidence_refs)) != len(item.evidence_refs)
                or not item.source_missing and not item.evidence_refs
                or type(item.capability_refs) is not tuple or len(item.capability_refs) > 200
                or any(type(ref) is not HandoverCapabilityItemRef
                       or type(ref.capability_item_id) is not uuid.UUID
                       or ref.capability_item_id.int == 0 for ref in item.capability_refs)
                or len({ref.capability_item_id for ref in item.capability_refs})
                   != len(item.capability_refs)
                or type(item.options) is not tuple or len(item.options) > 20
                or any(type(option) is not HandoverItemOptionDraft
                       for option in item.options)
                or len({option.option_code for option in item.options}) != len(item.options)):
            raise HandoverVersionCreateError("VALIDATION_FAILED")
        for option in item.options:
            if (not isinstance(option.option_code, str)
                    or not option.option_code or len(option.option_code) > 32
                    or not option.option_code[0].isalpha()
                    or option.option_code.upper() != option.option_code
                    or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                           for char in option.option_code)
                    or not text(option.label, 255)
                    or option.description is not None and not text(option.description, 2000)):
                raise HandoverVersionCreateError("VALIDATION_FAILED")
        if item.item_type == "NEED_CONFIRM":
            fields = item.required_input_spec.get("fields")
            if (item.confirmation_question is None or item.recommendation is None
                    or len(item.options) < 2 or not isinstance(fields, list)
                    or not 1 <= len(fields) <= 32
                    or any(not HandoverVersionCreateService._valid_input_field(value)
                           for value in fields)):
                raise HandoverVersionCreateError("VALIDATION_FAILED")
        elif (item.confirmation_question is not None or item.options
              or item.required_input_spec):
            raise HandoverVersionCreateError("VALIDATION_FAILED")

    @staticmethod
    def _valid_input_field(value: object) -> bool:
        if not isinstance(value, dict) or set(value) != {"name", "format", "example", "required"}:
            return False
        return (type(value["name"]) is str and 1 <= len(value["name"]) <= 128
                and value["name"] == value["name"].strip()
                and type(value["format"]) is str and 1 <= len(value["format"]) <= 128
                and value["format"] == value["format"].strip()
                and type(value["example"]) is str and 1 <= len(value["example"]) <= 500
                and value["example"] == value["example"].strip()
                and type(value["required"]) is bool)

    @staticmethod
    def _item_payload(item: HandoverAnalysisItemDraft) -> dict[str, object]:
        return {
            "analysis_item_id": str(item.analysis_item_id), "item_type": item.item_type,
            "title": item.title, "statement": item.statement, "impact": item.impact,
            "severity": item.severity, "priority": item.priority,
            "recommendation": item.recommendation,
            "confirmation_question": item.confirmation_question,
            "required_input_spec": item.required_input_spec,
            "source_missing": item.source_missing,
            "evidence_refs": [str(ref) for ref in item.evidence_refs],
            "capability_refs": [str(ref.capability_item_id)
                                for ref in item.capability_refs],
            "options": [{"option_code": option.option_code, "label": option.label,
                         "description": option.description} for option in item.options],
        }

    def _validate_capability(self, tx: object, command: CreateHandoverVersion
                             ) -> frozenset[uuid.UUID]:
        version = self._capabilities.get_version(
            tx, visibility="CURRENT_APPROVED",
            baseline_id=command.capability_baseline_id,
            baseline_version_id=command.capability_baseline_version_id,
        )
        if (type(version) is not CapabilityVersionView
                or version.baseline_id != command.capability_baseline_id
                or version.baseline_version_id != command.capability_baseline_version_id
                or version.state != "APPROVED"):
            raise HandoverVersionCreateError("HANDOVER_CAPABILITY_UNAVAILABLE")
        items = self._capabilities.list_items(
            tx, visibility="CURRENT_APPROVED",
            baseline_id=command.capability_baseline_id,
            baseline_version_id=command.capability_baseline_version_id,
            after_ordinal=None, limit=501,
        )
        if len(items) != version.declared_item_count or len(items) > 500:
            raise HandoverVersionCreateError("HANDOVER_CAPABILITY_UNAVAILABLE")
        return frozenset(item.capability_item_id for item in items if item.state == "AVAILABLE")

    def _validate_evidence(self, tx: object, command: CreateHandoverVersion) -> None:
        sources = {(ref.document_id, ref.document_version_id)
                   for ref in command.source_documents}
        for item in command.items:
            for evidence_id in item.evidence_refs:
                source = self._evidence.get_for_trace(
                    tx, scope="PROJECT", project_id=command.project_id,
                    evidence_id=evidence_id,
                )
                if (type(source) is not LockedEvidenceSource
                        or source.evidence_id != evidence_id
                        or source.scope != "PROJECT" or source.project_id != command.project_id
                        or (source.document_id, source.document_version_id) not in sources
                        or type(source.content_fingerprint) is not bytes
                        or len(source.content_fingerprint) != 32
                        or type(source.lock_version) is not int or source.lock_version < 0):
                    raise HandoverVersionCreateError("HANDOVER_EVIDENCE_UNAVAILABLE")

    @staticmethod
    def _validate_capability_refs(items: tuple[HandoverAnalysisItemDraft, ...],
                                  allowed: frozenset[uuid.UUID]) -> None:
        if any(ref.capability_item_id not in allowed
               for item in items for ref in item.capability_refs):
            raise HandoverVersionCreateError("HANDOVER_CAPABILITY_UNAVAILABLE")

    def _validate_ai_tasks(self, tx: object, command: CreateHandoverVersion) -> None:
        for task_id in command.ai_task_refs:
            task = self._ai_tasks.get(
                tx, ai_task_id=task_id, project_id=command.project_id,
            )
            if (type(task) is not AITaskView or task.ai_task_id != task_id
                    or task.project_id != command.project_id
                    or task.task_type != "GAP_ANALYSIS" or task.task_state != "SUCCEEDED"):
                raise HandoverVersionCreateError("HANDOVER_AI_PROVENANCE_UNAVAILABLE")

    def _actor(self, tx: object, command: CreateHandoverVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HandoverVersionCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise HandoverVersionCreateError("AUTH_ACCESS_DENIED")
        return actor
