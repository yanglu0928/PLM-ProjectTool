"""Exactly one admitted Provider Test Job; no process loop or production wiring."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.ai.application.publish_provider_probe_failure import (
    ProviderProbeFailureError, ProviderProbeFailureOutcome,
)
from plm_assistant.modules.ai.application.publish_provider_probe_success import ProviderProbePublicationError
from plm_assistant.modules.ai.application.run_provider_probe import (
    ProviderProbeExecutionError, ProviderProbeObservation,
)
from plm_assistant.modules.jobs.application.ai_provider_test_claim import (
    AIProviderTestClaim, AIProviderTestClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService


class ProviderProbeWorkerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProviderProbeWorkerCycle:
    state: str
    job_id: uuid.UUID | None = None
    result_id: uuid.UUID | None = None


class _Runner(Protocol):
    def run(self, *, job_id: uuid.UUID, fencing_token: int,
            worker_ref: str, trace_id: uuid.UUID) -> ProviderProbeObservation: ...


class _Success(Protocol):
    def publish(self, *, observation: ProviderProbeObservation,
                worker_ref: str, trace_id: uuid.UUID) -> uuid.UUID: ...


class _Failure(Protocol):
    def publish(self, *, job_id: uuid.UUID, fencing_token: int,
                worker_ref: str, trace_id: uuid.UUID,
                error: Exception) -> ProviderProbeFailureOutcome: ...


class ProviderProbeOneShotWorker:
    LEASE_SECONDS = 60

    def __init__(self, *, claims: AIProviderTestClaims, runner: _Runner,
                 success: _Success, failure: _Failure) -> None:
        if any(value is None for value in (claims, runner, success, failure)):
            raise ValueError("Provider probe Worker dependencies required")
        self._claims, self._runner = claims, runner
        self._success, self._failure = success, failure

    def run_once(self, *, worker_ref: str) -> ProviderProbeWorkerCycle:
        try:
            JobLeaseService._validate_worker(worker_ref)
            claim = self._claims.claim_next(
                worker_ref=worker_ref, lease_seconds=self.LEASE_SECONDS,
            )
        except JobLeaseError:
            raise ProviderProbeWorkerError("JOB_STORE_UNAVAILABLE") from None
        except Exception:
            raise ProviderProbeWorkerError("JOB_STORE_UNAVAILABLE") from None
        if claim is None:
            return ProviderProbeWorkerCycle("IDLE")
        if type(claim) is not AIProviderTestClaim:
            raise ProviderProbeWorkerError("JOB_STORE_UNAVAILABLE")
        try:
            claim.__post_init__()
        except JobLeaseError:
            raise ProviderProbeWorkerError("JOB_STORE_UNAVAILABLE") from None
        try:
            try:
                observation = self._runner.run(
                    job_id=claim.job_id, fencing_token=claim.fencing_token,
                    worker_ref=worker_ref, trace_id=claim.trace_id,
                )
                if (type(observation) is not ProviderProbeObservation
                        or observation.job_id != claim.job_id
                        or observation.fencing_token != claim.fencing_token
                        or observation.outcome != "SUCCEEDED"):
                    raise ProviderProbeExecutionError("PROBE_FACTS_CHANGED")
                result_id = self._success.publish(
                    observation=observation, worker_ref=worker_ref,
                    trace_id=claim.trace_id,
                )
                if type(result_id) is not uuid.UUID or not result_id.int:
                    raise ProviderProbePublicationError("AI_PROVIDER_UNAVAILABLE")
                return ProviderProbeWorkerCycle("SUCCEEDED", claim.job_id, result_id)
            except (ProviderProbeExecutionError, ProviderProbePublicationError) as exc:
                failure = exc
            except Exception:
                failure = ProviderProbeExecutionError("PROBE_UNAVAILABLE")
            failed = self._failure.publish(
                job_id=claim.job_id, fencing_token=claim.fencing_token,
                worker_ref=worker_ref, trace_id=claim.trace_id,
                error=failure,
            )
            if (type(failed) is not ProviderProbeFailureOutcome
                    or failed.job_state not in {"RETRY_WAIT", "FAILED"}
                    or (failed.job_state == "RETRY_WAIT" and failed.result_id is not None)
                    or (failed.job_state == "FAILED"
                        and (type(failed.result_id) is not uuid.UUID or not failed.result_id.int))):
                raise ProviderProbeWorkerError("JOB_STORE_UNAVAILABLE")
            return ProviderProbeWorkerCycle(failed.job_state, claim.job_id, failed.result_id)
        except ProviderProbeWorkerError:
            raise
        except ProviderProbeFailureError as exc:
            raise ProviderProbeWorkerError(exc.code) from None
        except Exception:
            raise ProviderProbeWorkerError("AI_PROVIDER_UNAVAILABLE") from None
