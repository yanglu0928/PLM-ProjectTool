"""Fenced Provider probe failure, bounded retry and terminal proof."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.jobs.application.ai_provider_test_claim import (
    AIProviderTestClaim, AIProviderTestClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint


_RETRYABLE = frozenset({
    "PROBE_DESTINATION_UNAVAILABLE", "PROBE_NETWORK_UNAVAILABLE",
    "PROBE_UNAVAILABLE", "AI_PROVIDER_UNAVAILABLE",
})
_FATAL = frozenset({
    "PROBE_DESTINATION_REJECTED", "PROBE_HTTP_REJECTED",
    "PROBE_PROTOCOL_REJECTED", "PROBE_RESPONSE_TOO_LARGE",
    "PROBE_SECRET_REJECTED", "PROBE_SECRET_UNAVAILABLE",
    "PROBE_FACTS_CHANGED", "AI_PROVIDER_CONFIG_CHANGED",
    "AI_PROVIDER_POLICY_CHANGED", "AI_PROVIDER_SECRET_CHANGED",
    "LICENSE_OPERATION_DENIED", "JOB_STORE_UNAVAILABLE",
    "VALIDATION_FAILED",
})


class ProviderProbeFailureError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProviderProbeFailureOutcome:
    job_state: str
    result_id: uuid.UUID | None


class _Jobs(Protocol):
    def retry_or_fail(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str, error_code: str,
                      retryable: bool, delay_seconds: int) -> str: ...


class _Results(Protocol):
    def append_failure(self, transaction: object, *, claim: AIProviderTestClaim,
                       failure_code: str) -> uuid.UUID: ...


def classify_provider_probe_failure(error: Exception, *,
                                    attempt_no: int) -> tuple[str, bool, int]:
    if not isinstance(error, Exception) or type(attempt_no) is not int or not 1 <= attempt_no <= 3:
        raise ProviderProbeFailureError("VALIDATION_FAILED")
    candidate = getattr(error, "code", None)
    if candidate == "JOB_LEASE_LOST":
        raise ProviderProbeFailureError("JOB_LEASE_LOST")
    code = candidate if type(candidate) is str and candidate in (_RETRYABLE | _FATAL) else "PROBE_UNAVAILABLE"
    retryable = code in _RETRYABLE and attempt_no < 3
    return code, retryable, ({1: 5, 2: 15, 3: 0}[attempt_no] if retryable else 0)


class ProviderProbeFailurePublisher:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: AIProviderTestClaims, jobs: _Jobs,
                 results: _Results, audit: ProviderProbeAudit) -> None:
        if any(value is None for value in (unit_of_work, claims, jobs, results, audit)):
            raise ValueError("Provider probe failure dependencies required")
        self._uow, self._claims, self._jobs = unit_of_work, claims, jobs
        self._results, self._audit = results, audit

    def publish(self, *, job_id: uuid.UUID, fencing_token: int,
                worker_ref: str, trace_id: uuid.UUID,
                error: Exception) -> ProviderProbeFailureOutcome:
        try:
            validate_checkpoint(job_id=job_id, fencing_token=fencing_token,
                                worker_ref=worker_ref)
        except JobLeaseError:
            raise ProviderProbeFailureError("VALIDATION_FAILED") from None
        if type(trace_id) is not uuid.UUID or not trace_id.int or not isinstance(error, Exception):
            raise ProviderProbeFailureError("VALIDATION_FAILED")
        try:
            identity = self._audit.capture()
            with self._uow() as tx:
                claim = self._claims.check_current(
                    tx, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                if type(claim) is not AIProviderTestClaim or claim.trace_id != trace_id:
                    raise ProviderProbeFailureError("JOB_STORE_UNAVAILABLE")
                code, retryable, delay = classify_provider_probe_failure(
                    error, attempt_no=claim.attempt_no,
                )
                state = self._jobs.retry_or_fail(
                    tx, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref, error_code=code,
                    retryable=retryable, delay_seconds=delay,
                )
                if state != ("RETRY_WAIT" if retryable else "FAILED"):
                    raise ProviderProbeFailureError("JOB_STORE_UNAVAILABLE")
                result_id = None
                if state == "FAILED":
                    result_id = self._results.append_failure(
                        tx, claim=claim, failure_code=code,
                    )
                    if type(result_id) is not uuid.UUID or not result_id.int:
                        raise ProviderProbeFailureError("JOB_STORE_UNAVAILABLE")
                self._audit.append(
                    tx, claim=claim, actor_id=identity,
                    action="AI_PROVIDER_TEST_RETRY" if retryable else "AI_PROVIDER_TEST_FAILED",
                    outcome="FAILED", state=state, reason_code=code,
                )
                self._audit.assert_same(identity)
                tx.commit()
                return ProviderProbeFailureOutcome(state, result_id)
        except ProviderProbeFailureError:
            raise
        except JobLeaseError:
            raise ProviderProbeFailureError("JOB_LEASE_LOST") from None
        except Exception:
            raise ProviderProbeFailureError("AI_PROVIDER_UNAVAILABLE") from None
