from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.fail_generation import (
    FAILURE_CODES,
    OutputGenerationFailureError,
    OutputGenerationFailureFacts,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork

_WORKER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", re.ASCII)


class PluginExecutionFailureError(RuntimeError):
    """Fixed, non-sensitive rejection for terminal plugin execution failure."""

    def __init__(self) -> None:
        self.code = "PLUGIN_EXECUTION_NOT_FAILABLE"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class PluginExecutionFailureFacts:
    plugin_execution_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    output_request_id: uuid.UUID
    output_context_snapshot_id: uuid.UUID
    attempt_no: int
    trace_id: uuid.UUID
    execution_state: str
    lock_version: int
    changed: bool


@dataclass(frozen=True, slots=True)
class PluginExecutionFailureResult:
    plugin_execution_id: uuid.UUID
    execution_state: str
    changed: bool


class PluginExecutionOutputFailurePort(Protocol):
    def fail_in_transaction(
        self, transaction: object, claim: ClaimedJob, *,
        worker_ref: str, error_code: str,
    ) -> OutputGenerationFailureFacts: ...


class PluginExecutionFailureRepositoryPort(Protocol):
    def lock_running(
        self, transaction: object, *, claim: ClaimedJob,
    ) -> PluginExecutionFailureFacts: ...
    def authorize_owner_writes(self, transaction: object) -> None: ...
    def fail_execution(
        self, transaction: object, *, claim: ClaimedJob,
        plugin_execution_id: uuid.UUID, expected_lock_version: int,
        error_code: str,
    ) -> PluginExecutionFailureFacts: ...
    def append_failed_event(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        project_id: uuid.UUID, trace_id: uuid.UUID, error_code: str,
    ) -> None: ...


class PluginExecutionFailureOwner:
    """Atomically fail Output, its Job and a RUNNING PluginExecution."""

    def __init__(
        self, *, unit_of_work: Callable[[], UnitOfWork],
        output_failure: PluginExecutionOutputFailurePort,
        repository: PluginExecutionFailureRepositoryPort,
        audit: AuditService,
    ) -> None:
        if any(value is None for value in (unit_of_work, output_failure, repository, audit)):
            raise ValueError("PluginExecution failure dependencies are required")
        self._uow = unit_of_work
        self._output = output_failure
        self._repository = repository
        self._audit = audit

    def fail(
        self, claim: ClaimedJob, *, worker_ref: str, error_code: str,
    ) -> PluginExecutionFailureResult:
        self._validate(claim, worker_ref, error_code)
        try:
            with self._uow() as transaction:
                output = self._output.fail_in_transaction(
                    transaction, claim, worker_ref=worker_ref, error_code=error_code,
                )
                request_id, context_id = self._payload_ids(claim.payload_refs)
                if (type(output) is not OutputGenerationFailureFacts
                        or output.output_request_id != request_id
                        or output.context_snapshot_id != context_id
                        or output.project_id != claim.project_id
                        or output.job_id != claim.job_id
                        or output.state != "FAILED" or not output.changed):
                    raise PluginExecutionFailureError()

                candidate = self._repository.lock_running(transaction, claim=claim)
                if (type(candidate) is not PluginExecutionFailureFacts
                        or candidate.project_id != claim.project_id
                        or candidate.job_id != claim.job_id
                        or candidate.output_request_id != request_id
                        or candidate.output_context_snapshot_id != context_id
                        or candidate.attempt_no != claim.attempt_no
                        or candidate.execution_state != "RUNNING"
                        or candidate.changed
                        or type(candidate.plugin_execution_id) is not uuid.UUID
                        or not candidate.plugin_execution_id.int
                        or type(candidate.trace_id) is not uuid.UUID
                        or not candidate.trace_id.int
                        or type(candidate.lock_version) is not int
                        or candidate.lock_version < 1):
                    raise PluginExecutionFailureError()

                self._repository.authorize_owner_writes(transaction)
                failed = self._repository.fail_execution(
                    transaction, claim=claim,
                    plugin_execution_id=candidate.plugin_execution_id,
                    expected_lock_version=candidate.lock_version,
                    error_code=error_code,
                )
                if (type(failed) is not PluginExecutionFailureFacts
                        or failed.plugin_execution_id != candidate.plugin_execution_id
                        or failed.project_id != claim.project_id
                        or failed.job_id != claim.job_id
                        or failed.output_request_id != request_id
                        or failed.output_context_snapshot_id != context_id
                        or failed.attempt_no != claim.attempt_no
                        or failed.trace_id != candidate.trace_id
                        or failed.execution_state != "FAILED"
                        or failed.lock_version != candidate.lock_version + 1
                        or failed.changed is not True):
                    raise PluginExecutionFailureError()

                self._repository.append_failed_event(
                    transaction,
                    plugin_execution_id=failed.plugin_execution_id,
                    project_id=failed.project_id, trace_id=failed.trace_id,
                    error_code=error_code,
                )
                self._audit.append(
                    transaction,
                    AuditEventDraft(
                        trace_id=failed.trace_id, event_scope="PROJECT",
                        target_project_id=failed.project_id,
                        actor_type="UNRESOLVED", actor_id=None,
                        original_actor_id=None, actor_hint_digest=None,
                        action="PLUGIN_EXECUTION_FAILED", outcome="FAILED",
                        target_owner_module="plugin",
                        target_object_type="PLG-03",
                        target_object_id=failed.plugin_execution_id,
                        before_state="RUNNING", after_state="FAILED",
                    ),
                )
                transaction.commit()
                return PluginExecutionFailureResult(
                    failed.plugin_execution_id, "FAILED", True,
                )
        except PluginExecutionFailureError:
            raise
        except (OutputGenerationFailureError, JobLeaseError, IdempotencyError):
            raise PluginExecutionFailureError() from None
        except Exception:
            raise PluginExecutionFailureError() from None

    @staticmethod
    def _validate(claim: object, worker_ref: object, error_code: object) -> None:
        if (type(claim) is not ClaimedJob
                or claim.job_type != "OUTPUT_GENERATE"
                or claim.scope != "PROJECT"
                or type(claim.job_id) is not uuid.UUID or not claim.job_id.int
                or type(claim.project_id) is not uuid.UUID or not claim.project_id.int
                or type(claim.fencing_token) is not int or claim.fencing_token < 1
                or type(claim.attempt_no) is not int or claim.attempt_no != 1
                or type(worker_ref) is not str or _WORKER.fullmatch(worker_ref) is None
                or type(error_code) is not str or error_code not in FAILURE_CODES):
            raise PluginExecutionFailureError()
        PluginExecutionFailureOwner._payload_ids(claim.payload_refs)
        try:
            trace_id = uuid.UUID(claim.trace_id)
        except (TypeError, ValueError, AttributeError):
            raise PluginExecutionFailureError() from None
        if str(trace_id) != claim.trace_id or not trace_id.int:
            raise PluginExecutionFailureError()

    @staticmethod
    def _payload_ids(value: object) -> tuple[uuid.UUID, uuid.UUID]:
        if type(value) is not dict or set(value) != {
            "output_request_id", "context_snapshot_id",
        }:
            raise PluginExecutionFailureError()
        parsed = []
        for key in ("output_request_id", "context_snapshot_id"):
            raw = value.get(key)
            try:
                item = uuid.UUID(raw)
            except (TypeError, ValueError, AttributeError):
                raise PluginExecutionFailureError() from None
            if type(raw) is not str or str(item) != raw or not item.int:
                raise PluginExecutionFailureError()
            parsed.append(item)
        return parsed[0], parsed[1]
