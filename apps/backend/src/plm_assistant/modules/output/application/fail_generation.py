"""Atomic terminal failure transition for Output and its active Job lease."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError


class OutputGenerationFailureError(RuntimeError):
    def __init__(self, code: str = "OUTPUT_FAILURE_NOT_ELIGIBLE") -> None:
        self.code = code
        super().__init__(code)


FAILURE_CODES = frozenset({
    "OUTPUT_GENERATION_FAILED",
    "OUTPUT_PLUGIN_UNAVAILABLE",
    "OUTPUT_VALIDATION_FAILED",
})


@dataclass(frozen=True, slots=True)
class OutputGenerationFailureFacts:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    context_snapshot_id: uuid.UUID
    requested_by: uuid.UUID
    execution_id: uuid.UUID
    state: str
    lock_version: int
    changed: bool


class OutputGenerationFailureRepositoryPort(Protocol):
    def lock_candidate(self, transaction: object, *, claim: ClaimedJob,
                       execution_id: uuid.UUID) -> OutputGenerationFailureFacts: ...
    def fail_generation(self, transaction: object, *, claim: ClaimedJob,
                        execution_id: uuid.UUID, expected_lock_version: int
                        ) -> OutputGenerationFailureFacts: ...


class OutputGenerationFailureJobsPort(Protocol):
    def check_output_claim(self, transaction: object, *, job_id: uuid.UUID,
                           fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def retry_or_fail(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str, error_code: str,
                      retryable: bool, delay_seconds: int) -> str: ...


class OutputGenerationFailureOwner:
    """Terminalize an irreversible Output failure under the current fenced lease."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 jobs: OutputGenerationFailureJobsPort,
                 repository: OutputGenerationFailureRepositoryPort,
                 audit: AuditService, system_actor_id: uuid.UUID) -> None:
        if (unit_of_work is None or jobs is None or repository is None or audit is None
                or type(system_actor_id) is not uuid.UUID or not system_actor_id.int):
            raise ValueError("Output generation failure dependencies are required")
        self._uow, self._jobs, self._repo, self._audit = unit_of_work, jobs, repository, audit
        self._system_actor_id = system_actor_id

    def fail(self, claim: ClaimedJob, *, worker_ref: str, error_code: str
             ) -> OutputGenerationFailureFacts:
        request_id, snapshot_id, trace_id = self._validate_claim(claim, worker_ref)
        if type(error_code) is not str or error_code not in FAILURE_CODES:
            raise OutputGenerationFailureError()
        execution_id = uuid.uuid5(claim.job_id, "output-generation:" + str(claim.fencing_token))
        try:
            with self._uow() as transaction:
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
                    raise OutputGenerationFailureError()
                current = self._jobs.check_output_claim(
                    transaction, job_id=claim.job_id,
                    fencing_token=claim.fencing_token, worker_ref=worker_ref,
                )
                if (type(current) is not ClaimedJob or current != claim
                        or current.job_type != "OUTPUT_GENERATE"
                        or current.project_id != claim.project_id
                        or current.payload_refs != claim.payload_refs):
                    raise OutputGenerationFailureError()
                job_state = self._jobs.retry_or_fail(
                    transaction, job_id=claim.job_id,
                    fencing_token=claim.fencing_token, worker_ref=worker_ref,
                    error_code=error_code, retryable=False, delay_seconds=0,
                )
                if job_state != "FAILED":
                    raise OutputGenerationFailureError()
                facts = self._repo.fail_generation(
                    transaction, claim=claim, execution_id=execution_id,
                    expected_lock_version=candidate.lock_version,
                )
                if (type(facts) is not OutputGenerationFailureFacts
                        or facts.output_request_id != request_id
                        or facts.context_snapshot_id != snapshot_id
                        or facts.job_id != claim.job_id
                        or facts.project_id != claim.project_id
                        or facts.execution_id != execution_id
                        or facts.state != "FAILED" or facts.lock_version != candidate.lock_version + 1
                        or not facts.changed):
                    raise OutputGenerationFailureError()
                self._audit.append(transaction, AuditEventDraft(
                    trace_id=trace_id, event_scope="PROJECT",
                    target_project_id=facts.project_id, actor_type="SYSTEM",
                    actor_id=self._system_actor_id, original_actor_id=facts.requested_by,
                    actor_hint_digest=None, action="OUTPUT_GENERATION_FAILED",
                    outcome="FAILED", target_owner_module="output",
                    target_object_type="OUT-01", target_object_id=facts.output_request_id,
                    before_state="GENERATING", after_state="FAILED",
                ))
                transaction.commit()
                return facts
        except OutputGenerationFailureError:
            raise
        except (JobLeaseError, IdempotencyError):
            raise OutputGenerationFailureError() from None
        except Exception:
            raise OutputGenerationFailureError("SYSTEM_UNAVAILABLE") from None

    @staticmethod
    def _validate_claim(claim: ClaimedJob, worker_ref: str
                        ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        if (type(claim) is not ClaimedJob or claim.job_type != "OUTPUT_GENERATE"
                or claim.scope != "PROJECT"
                or type(claim.project_id) is not uuid.UUID or not claim.project_id.int
                or type(claim.job_id) is not uuid.UUID or not claim.job_id.int
                or type(claim.fencing_token) is not int or claim.fencing_token < 1
                or type(claim.attempt_no) is not int or claim.attempt_no < 1
                or type(worker_ref) is not str or not worker_ref.strip()
                or type(claim.payload_refs) is not dict
                or set(claim.payload_refs) != {"output_request_id", "context_snapshot_id"}):
            raise OutputGenerationFailureError()
        try:
            request_id = uuid.UUID(claim.payload_refs["output_request_id"])
            snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
            trace_id = uuid.UUID(claim.trace_id)
        except (TypeError, ValueError, AttributeError):
            raise OutputGenerationFailureError() from None
        if (str(request_id) != claim.payload_refs["output_request_id"]
                or str(snapshot_id) != claim.payload_refs["context_snapshot_id"]
                or not trace_id.int):
            raise OutputGenerationFailureError()
        return request_id, snapshot_id, trace_id
