"""Atomically retry a transient PluginExecution failure across Output and Jobs."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureError, OutputGenerationFailureOwner,
)
from plm_assistant.modules.output.application.retry_generation import (
    OutputGenerationRetryError, OutputGenerationRetryOwner, OutputGenerationRetryResult,
)
from plm_assistant.modules.plugin.application.execution_failure import (
    PluginExecutionFailureFacts,
)

_RETRYABLE_PLUGIN_CODES = frozenset({"OUTPUT_PLUGIN_BUSY"})
_WORKER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", re.ASCII)


class PluginExecutionRetryError(RuntimeError):
    def __init__(self, code: str = "PLUGIN_EXECUTION_RETRY_NOT_ELIGIBLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PluginExecutionRetryResult:
    facts: PluginExecutionFailureFacts
    job_state: str
    output_state: str
    retry_delay_seconds: int


class PluginExecutionRetryRepositoryPort(Protocol):
    def authorize_owner_writes(self, transaction: object) -> None: ...
    def lock_running(
        self, transaction: object, *, claim: ClaimedJob,
    ) -> PluginExecutionFailureFacts: ...
    def fail_retryable(
        self, transaction: object, *, claim: ClaimedJob,
        plugin_execution_id: uuid.UUID, expected_lock_version: int,
        error_code: str,
    ) -> PluginExecutionFailureFacts: ...
    def append_failed_event(
        self, transaction: object, *, plugin_execution_id: uuid.UUID,
        project_id: uuid.UUID, trace_id: uuid.UUID, error_code: str,
    ) -> None: ...


class PluginExecutionRetryOwner:
    """Persist a retryable Plugin failure with Output and Job in one caller UoW."""

    def __init__(
        self, *, unit_of_work: Callable[[], object],
        output_retry: OutputGenerationRetryOwner,
        repository: PluginExecutionRetryRepositoryPort,
        audit: AuditService,
    ) -> None:
        if any(value is None for value in (unit_of_work, output_retry, repository, audit)):
            raise ValueError("PluginExecution retry dependencies are required")
        self._uow = unit_of_work
        self._output = output_retry
        self._repository = repository
        self._audit = audit

    def retry(
        self, claim: ClaimedJob, *, worker_ref: str, error_code: str,
    ) -> PluginExecutionRetryResult:
        self._validate(claim, worker_ref, error_code)
        try:
            with self._uow() as transaction:
                result = self.retry_in_transaction(
                    transaction, claim, worker_ref=worker_ref, error_code=error_code,
                )
                transaction.commit()
                return result
        except PluginExecutionRetryError:
            raise
        except (JobLeaseError, OutputGenerationFailureError, OutputGenerationRetryError):
            raise PluginExecutionRetryError() from None
        except Exception:
            raise PluginExecutionRetryError("SYSTEM_UNAVAILABLE") from None

    def retry_in_transaction(
        self, transaction: object, claim: ClaimedJob, *,
        worker_ref: str, error_code: str,
    ) -> PluginExecutionRetryResult:
        """Compose transaction-scoped Output retry and Plugin history; does not commit."""
        self._validate(claim, worker_ref, error_code)
        try:
            output: OutputGenerationRetryResult = self._output.retry_in_transaction(
                transaction, claim, worker_ref=worker_ref, error_code=error_code,
            )
            request_id, context_id, trace_id = self._validated_claim(claim, worker_ref)
            output_facts = output.facts
            target_state = "QUEUED" if output.job_state == "RETRY_WAIT" else "FAILED"
            if (type(output) is not OutputGenerationRetryResult
                    or output.job_state not in {"RETRY_WAIT", "FAILED"}
                    or output_facts.output_request_id != request_id
                    or output_facts.context_snapshot_id != context_id
                    or output_facts.project_id != claim.project_id
                    or output_facts.job_id != claim.job_id
                    or output_facts.state != target_state
                    or (output.job_state == "RETRY_WAIT" and output.retry_delay_seconds < 1)):
                raise PluginExecutionRetryError()

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
                raise PluginExecutionRetryError()

            self._repository.authorize_owner_writes(transaction)
            failed = self._repository.fail_retryable(
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
                raise PluginExecutionRetryError()

            self._repository.append_failed_event(
                transaction,
                plugin_execution_id=failed.plugin_execution_id,
                project_id=failed.project_id, trace_id=failed.trace_id,
                error_code=error_code,
            )
            scheduled = output.job_state == "RETRY_WAIT"
            self._audit.append(
                transaction,
                AuditEventDraft(
                    trace_id=failed.trace_id, event_scope="PROJECT",
                    target_project_id=failed.project_id, actor_type="UNRESOLVED",
                    actor_id=None, original_actor_id=None, actor_hint_digest=None,
                    action=("PLUGIN_EXECUTION_RETRY_SCHEDULED" if scheduled
                            else "PLUGIN_EXECUTION_RETRY_EXHAUSTED"),
                    outcome="SUCCESS" if scheduled else "FAILED",
                    target_owner_module="plugin", target_object_type="PLG-03",
                    target_object_id=failed.plugin_execution_id,
                    before_state="RUNNING", after_state="FAILED",
                ),
            )
            return PluginExecutionRetryResult(
                failed, output.job_state, output_facts.state,
                output.retry_delay_seconds,
            )
        except PluginExecutionRetryError:
            raise
        except (JobLeaseError, OutputGenerationFailureError, OutputGenerationRetryError):
            raise PluginExecutionRetryError() from None
        except Exception:
            raise PluginExecutionRetryError("SYSTEM_UNAVAILABLE") from None

    @staticmethod
    def _validate(
        claim: object, worker_ref: object, error_code: object,
    ) -> None:
        if (type(worker_ref) is not str or _WORKER.fullmatch(worker_ref) is None
                or type(error_code) is not str or error_code not in _RETRYABLE_PLUGIN_CODES):
            raise PluginExecutionRetryError()
        PluginExecutionRetryOwner._validated_claim(claim, worker_ref)

    @staticmethod
    def _validated_claim(claim: object, worker_ref: str):
        try:
            request_id, context_id, trace_id = OutputGenerationFailureOwner._validate_claim(
                claim, worker_ref,
            )
        except OutputGenerationFailureError:
            raise PluginExecutionRetryError() from None
        if (type(claim) is not ClaimedJob
                or type(claim.attempt_no) is not int or claim.attempt_no < 1):
            raise PluginExecutionRetryError()
        return request_id, context_id, trace_id
