"""Authorized, idempotent Checklist record command with registered Owners."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError,
)

from .append_checklist_record import (
    AppendChecklistRecord, ChecklistRecordAppendError,
    ChecklistRecordWriteLock,
)
from .checklist_qualification import (
    AggregateChecklistQualification,
    ChecklistQualificationError,
    CurrentChecklistQualification,
    CurrentChecklistQualificationQuery,
)
from .current_checklist_record import (
    ChecklistBasisObservation, ChecklistRecordReadError,
    CurrentChecklistRecord,
)
from ..domain.transition import ChecklistState


_OPERATION = "V1_WORKFLOW_CHECKLIST_RECORD"
_REGISTERED = frozenset({
    "HANDOVER_BASELINE", "HANDOVER_ISSUES",
    "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION",
    "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE",
})


class WorkflowChecklistRecordError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RecordWorkflowChecklist:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    item_key: str
    result: ChecklistState
    evidence_refs: tuple[uuid.UUID, ...]
    exception_refs: tuple[uuid.UUID, ...]
    expected_workflow_version: int
    reason: str | None = None
    impact: str | None = None


class ChecklistSessionPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes,
        csrf_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class ChecklistProjectPort(Protocol):
    def require_in_transaction(
        self, transaction: object, *, user_id: uuid.UUID,
        project_id: uuid.UUID, operation: str,
    ) -> AuthorizedProjectAction: ...


class ChecklistLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ChecklistQualificationPort(Protocol):
    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> CurrentChecklistQualification | AggregateChecklistQualification: ...


class ChecklistAppendPort(Protocol):
    def lock_current(
        self, transaction: object, *, project_id: uuid.UUID,
        item_key: str, expected_workflow_version: int,
    ) -> ChecklistRecordWriteLock: ...

    def append(
        self, transaction: object, *, lock: ChecklistRecordWriteLock,
        command: AppendChecklistRecord,
    ) -> CurrentChecklistRecord: ...


class ChecklistReplayPort(Protocol):
    def get_record(
        self, transaction: object, *, project_id: uuid.UUID,
        item_key: str, record_id: uuid.UUID,
    ) -> CurrentChecklistRecord | None: ...


class ChecklistReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class WorkflowChecklistRecordService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        sessions: ChecklistSessionPort, projects: ChecklistProjectPort,
        license_guard: ChecklistLicensePort,
        qualification: ChecklistQualificationPort,
        appender: ChecklistAppendPort, replay: ChecklistReplayPort,
        receipts: ChecklistReceiptPort, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, sessions, projects, license_guard,
                qualification, appender, replay, receipts, audit)):
            raise ValueError("Workflow Checklist dependencies required")
        self._uow, self._sessions, self._projects = (
            unit_of_work, sessions, projects,
        )
        self._guard, self._qualification = license_guard, qualification
        self._appender, self._replay = appender, replay
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def record(
        self, command: RecordWorkflowChecklist, *, idempotency_key: str,
    ) -> CurrentChecklistRecord:
        self._validate(command)
        try:
            validate_idempotency_key(idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "item_key": command.item_key,
                "result": command.result.value,
                "evidence_refs": sorted(str(value)
                                        for value in command.evidence_refs),
                "exception_refs": sorted(str(value)
                                         for value in command.exception_refs),
                "expected_workflow_version": (
                    command.expected_workflow_version
                ),
                "reason": command.reason,
                "impact": command.impact,
            })
            with self._uow() as tx:
                self._actor(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                proof = self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="WORKFLOW_CHECKLIST_RECORD",
                )
                if (type(proof) is not AuthorizedProjectAction
                        or proof.user_id != actor
                        or proof.project_id != command.project_id
                        or proof.operation != "WORKFLOW_CHECKLIST_RECORD"
                        or proof.project_role != "PROJECT_MANAGER"):
                    raise WorkflowChecklistRecordError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope,
                    request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    return self._recover(tx, command, replay)
                basis = self._basis(tx, command)
                lock = self._appender.lock_current(
                    tx, project_id=command.project_id,
                    item_key=command.item_key,
                    expected_workflow_version=(
                        command.expected_workflow_version
                    ),
                )
                current = self._appender.append(
                    tx, lock=lock,
                    command=AppendChecklistRecord(
                        actor, command.trace_id, command.result, basis,
                        self._now(), command.reason, command.impact,
                    ),
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="WORKFLOW_CHECKLIST_RECORDED",
                    outcome="SUCCESS", target_owner_module="workflow",
                    target_object_type="WFL-01",
                    target_object_id=current.record.workflow_id,
                    target_version_id=current.record.record_id,
                    before_state=current.record.before_state.value,
                    after_state=current.record.result.value,
                ))
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(
                        _OPERATION, current.record.record_id, 200,
                    ),
                )
                tx.commit()
                return current
        except WorkflowChecklistRecordError:
            raise
        except ChecklistRecordAppendError as error:
            raise WorkflowChecklistRecordError(error.code) from None
        except (ChecklistRecordReadError, ChecklistQualificationError):
            raise WorkflowChecklistRecordError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            ) from None
        except ProjectAuthorizationError as error:
            raise WorkflowChecklistRecordError(error.code) from None
        except RuntimeLicenseError:
            raise WorkflowChecklistRecordError(
                "LICENSE_OPERATION_DENIED",
            ) from None
        except IdempotencyError as error:
            raise WorkflowChecklistRecordError(error.code) from None
        except Exception:
            raise WorkflowChecklistRecordError("WORKFLOW_UNAVAILABLE") from None

    def _basis(
        self, tx: object, command: RecordWorkflowChecklist,
    ) -> tuple[ChecklistBasisObservation, ...]:
        if command.result is ChecklistState.FAIL:
            return ()
        if command.result is not ChecklistState.PASS:
            raise WorkflowChecklistRecordError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )
        result = self._qualification.qualify_only_current_in_transaction(
            tx, CurrentChecklistQualificationQuery(
                command.session_token, command.trace_id,
                command.project_id, command.item_key,
            ),
        )
        if type(result) in {
                CurrentChecklistQualification,
                AggregateChecklistQualification}:
            result.__post_init__()
        if (type(result) not in {
                CurrentChecklistQualification,
                AggregateChecklistQualification}
                or result.project_id != command.project_id
                or result.item_key != command.item_key):
            raise WorkflowChecklistRecordError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )
        if type(result) is AggregateChecklistQualification:
            if set(command.evidence_refs) != set(result.evidence_refs):
                raise WorkflowChecklistRecordError(
                    "WORKFLOW_GATE_NOT_SATISFIED",
                )
            return self._aggregate_basis(result)
        if set(command.evidence_refs) != {
                value.evidence_id for value in result.evidence}:
            raise WorkflowChecklistRecordError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )
        values = [ChecklistBasisObservation(
            "EVIDENCE", value.evidence_id, "PROJECT", value.project_id,
            "ELIGIBLE", value.observed_lock_version,
            value.content_fingerprint, value.verified_at, 1,
        ) for value in result.evidence]
        values.append(ChecklistBasisObservation(
            "REVIEW_ROUND", result.review.review_round_id,
            "PROJECT", result.review.project_id, "APPROVED",
            result.review.observed_lock_version,
            result.content_fingerprint, result.review.verified_at, 1,
        ))
        return tuple(sorted(
            values, key=lambda value: (value.ref_kind, str(value.ref_id)),
        ))

    @staticmethod
    def _aggregate_basis(
        result: AggregateChecklistQualification,
    ) -> tuple[ChecklistBasisObservation, ...]:
        evidence = {}
        for observation in (
                *(value for subject in result.subjects
                  for value in subject.evidence),
                *result.scope_evidence):
            previous = evidence.setdefault(
                observation.evidence_id, observation,
            )
            if previous != observation:
                raise WorkflowChecklistRecordError(
                    "WORKFLOW_GATE_NOT_SATISFIED",
                )
        values = [ChecklistBasisObservation(
            "EVIDENCE", value.evidence_id, "PROJECT", value.project_id,
            "ELIGIBLE", value.observed_lock_version,
            value.content_fingerprint, value.verified_at, 1,
        ) for value in evidence.values()]
        values.extend(ChecklistBasisObservation(
            "REVIEW_ROUND", subject.review.review_round_id, "PROJECT",
            subject.review.project_id, "APPROVED",
            subject.review.observed_lock_version,
            subject.content_fingerprint, subject.review.verified_at, 1,
        ) for subject in result.subjects)
        return tuple(sorted(
            values, key=lambda value: (value.ref_kind, str(value.ref_id)),
        ))

    def _recover(
        self, tx: object, command: RecordWorkflowChecklist,
        result: IdempotencyResult,
    ) -> CurrentChecklistRecord:
        if (type(result) is not IdempotencyResult
                or result.ref_type != _OPERATION
                or result.status_code != 200):
            raise WorkflowChecklistRecordError("WORKFLOW_UNAVAILABLE")
        current = self._replay.get_record(
            tx, project_id=command.project_id,
            item_key=command.item_key, record_id=result.ref_id,
        )
        if (type(current) is not CurrentChecklistRecord
                or current.record.project_id != command.project_id
                or current.record.item_key != command.item_key
                or current.record.result is not command.result):
            raise WorkflowChecklistRecordError("WORKFLOW_UNAVAILABLE")
        return current

    @staticmethod
    def _validate(command: RecordWorkflowChecklist) -> None:
        refs = (getattr(command, "evidence_refs", None),
                getattr(command, "exception_refs", None))
        if (type(command) is not RecordWorkflowChecklist
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (command.trace_id, command.project_id))
                or command.item_key not in _REGISTERED
                or type(command.result) is not ChecklistState
                or command.result not in {
                    ChecklistState.PASS, ChecklistState.FAIL,
                    ChecklistState.WAIVED,
                }
                or any(type(values) is not tuple for values in refs)
                or any(type(value) is not uuid.UUID or value.int == 0
                       for values in refs for value in values)
                or any(len(set(values)) != len(values) for values in refs)
                or type(command.expected_workflow_version) is not int
                or not 0 <= command.expected_workflow_version < 2**63 - 1
                or any(value is not None and (
                    type(value) is not str or not 0 < len(value) <= 2000
                    or not value.strip() or "\x00" in value
                ) for value in (command.reason, command.impact))
        ):
            raise WorkflowChecklistRecordError("VALIDATION_FAILED")
        if command.result is ChecklistState.WAIVED:
            raise WorkflowChecklistRecordError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )
        if (command.exception_refs
                or command.result is ChecklistState.FAIL
                   and command.evidence_refs):
            raise WorkflowChecklistRecordError("VALIDATION_FAILED")

    def _actor(
        self, tx: object, command: RecordWorkflowChecklist,
    ) -> uuid.UUID:
        now = self._now()
        actor = self._sessions.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise WorkflowChecklistRecordError("AUTH_ACCESS_DENIED")
        return actor

    def _now(self) -> datetime:
        value = self._clock()
        if (type(value) is not datetime or value.tzinfo is None
                or value.utcoffset() is None):
            raise WorkflowChecklistRecordError("WORKFLOW_UNAVAILABLE")
        return value.astimezone(timezone.utc)
