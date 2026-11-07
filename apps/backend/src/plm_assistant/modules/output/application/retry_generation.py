"""Atomic Output retry scheduling under the active fenced Job lease."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureError, OutputGenerationFailureFacts, OutputGenerationFailureOwner,
)

RETRYABLE_OUTPUT_CODES = frozenset({
    "OUTPUT_GENERATION_TRANSIENT",
    "OUTPUT_PLUGIN_BUSY",
    "OUTPUT_STORAGE_TEMPORARY",
})
OUTPUT_RETRY_DELAY_SECONDS = 30


class OutputGenerationRetryError(RuntimeError):
    def __init__(self, code: str = "OUTPUT_RETRY_NOT_ELIGIBLE") -> None:
        self.code = code
        super().__init__(code)


class OutputGenerationRetryRepositoryPort(Protocol):
    def lock_candidate(self, transaction: object, *, claim: ClaimedJob,
                       execution_id: uuid.UUID) -> OutputGenerationFailureFacts: ...
    def transition_retry(self, transaction: object, *, claim: ClaimedJob,
                         execution_id: uuid.UUID, expected_lock_version: int,
                         target_state: str) -> OutputGenerationFailureFacts: ...


class OutputGenerationRetryJobsPort(Protocol):
    def check_output_claim(self, transaction: object, *, job_id: uuid.UUID,
                           fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def retry_or_fail(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str, error_code: str,
                      retryable: bool, delay_seconds: int) -> str: ...


@dataclass(frozen=True, slots=True)
class OutputGenerationRetryResult:
    facts: OutputGenerationFailureFacts
    job_state: str
    retry_delay_seconds: int


class OutputGenerationRetryOwner:
    """Move Job and Output together to RETRY_WAIT/QUEUED or exhausted FAILED."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 jobs: OutputGenerationRetryJobsPort,
                 repository: OutputGenerationRetryRepositoryPort,
                 audit: AuditService, system_actor_id: uuid.UUID) -> None:
        if (unit_of_work is None or jobs is None or repository is None or audit is None
                or type(system_actor_id) is not uuid.UUID or not system_actor_id.int):
            raise ValueError("Output generation retry dependencies are required")
        self._uow, self._jobs, self._repo, self._audit = unit_of_work, jobs, repository, audit
        self._system_actor_id = system_actor_id

    def retry(self, claim: ClaimedJob, *, worker_ref: str, error_code: str
              ) -> OutputGenerationRetryResult:
        try:
            OutputGenerationFailureOwner._validate_claim(claim, worker_ref)
        except OutputGenerationFailureError:
            raise OutputGenerationRetryError() from None
        if type(error_code) is not str or error_code not in RETRYABLE_OUTPUT_CODES:
            raise OutputGenerationRetryError()
        try:
            with self._uow() as transaction:
                result = self.retry_in_transaction(
                    transaction, claim, worker_ref=worker_ref, error_code=error_code,
                )
                transaction.commit()
                return result
        except OutputGenerationRetryError:
            raise
        except (JobLeaseError, OutputGenerationFailureError):
            raise OutputGenerationRetryError() from None
        except Exception:
            raise OutputGenerationRetryError("SYSTEM_UNAVAILABLE") from None

    def retry_in_transaction(
        self, transaction: object, claim: ClaimedJob, *,
        worker_ref: str, error_code: str,
    ) -> OutputGenerationRetryResult:
        """Apply retry state within a caller-owned UoW; never commits it."""
        try:
            request_id, snapshot_id, trace_id = OutputGenerationFailureOwner._validate_claim(
                claim, worker_ref)
            if type(error_code) is not str or error_code not in RETRYABLE_OUTPUT_CODES:
                raise OutputGenerationRetryError()
            execution_id = uuid.uuid5(
                claim.job_id, "output-generation:" + str(claim.fencing_token),
            )
            candidate = self._repo.lock_candidate(
                transaction, claim=claim, execution_id=execution_id,
            )
            if (type(candidate) is not OutputGenerationFailureFacts
                    or candidate.output_request_id != request_id
                    or candidate.context_snapshot_id != snapshot_id
                    or candidate.job_id != claim.job_id
                    or candidate.project_id != claim.project_id
                    or candidate.execution_id != execution_id
                    or candidate.state != "GENERATING" or candidate.changed
                    or candidate.lock_version < 1):
                raise OutputGenerationRetryError()
            current = self._jobs.check_output_claim(
                transaction, job_id=claim.job_id,
                fencing_token=claim.fencing_token, worker_ref=worker_ref,
            )
            if (type(current) is not ClaimedJob or current != claim
                    or current.job_type != "OUTPUT_GENERATE"
                    or current.project_id != claim.project_id
                    or current.payload_refs != claim.payload_refs):
                raise OutputGenerationRetryError()
            job_state = self._jobs.retry_or_fail(
                transaction, job_id=claim.job_id,
                fencing_token=claim.fencing_token, worker_ref=worker_ref,
                error_code=error_code, retryable=True,
                delay_seconds=OUTPUT_RETRY_DELAY_SECONDS,
            )
            target = {"RETRY_WAIT": "QUEUED", "FAILED": "FAILED"}.get(job_state)
            if target is None:
                raise OutputGenerationRetryError()
            facts = self._repo.transition_retry(
                transaction, claim=claim, execution_id=execution_id,
                expected_lock_version=candidate.lock_version, target_state=target,
            )
            if (type(facts) is not OutputGenerationFailureFacts
                    or facts.output_request_id != request_id
                    or facts.context_snapshot_id != snapshot_id
                    or facts.job_id != claim.job_id or facts.project_id != claim.project_id
                    or facts.execution_id != execution_id or facts.state != target
                    or facts.lock_version != candidate.lock_version + 1
                    or not facts.changed):
                raise OutputGenerationRetryError()
            action = ("OUTPUT_GENERATION_RETRY_SCHEDULED"
                      if job_state == "RETRY_WAIT"
                      else "OUTPUT_GENERATION_RETRY_EXHAUSTED")
            self._audit.append(transaction, AuditEventDraft(
                trace_id=trace_id, event_scope="PROJECT",
                target_project_id=facts.project_id, actor_type="SYSTEM",
                actor_id=self._system_actor_id, original_actor_id=facts.requested_by,
                actor_hint_digest=None, action=action,
                outcome="SUCCESS" if job_state == "RETRY_WAIT" else "FAILED",
                target_owner_module="output", target_object_type="OUT-01",
                target_object_id=facts.output_request_id,
                before_state="GENERATING", after_state=target,
            ))
            return OutputGenerationRetryResult(
                facts, job_state,
                OUTPUT_RETRY_DELAY_SECONDS if job_state == "RETRY_WAIT" else 0,
            )
        except OutputGenerationRetryError:
            raise
        except (JobLeaseError, OutputGenerationFailureError):
            raise OutputGenerationRetryError() from None
        except Exception:
            raise OutputGenerationRetryError("SYSTEM_UNAVAILABLE") from None
