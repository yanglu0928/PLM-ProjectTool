"""Exactly one business AI Task execution; no process loop or composition root."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob,
    JobLeaseError,
    JobLeaseService,
)

from .complete_provider_failure import (
    AITaskProviderFailureError,
    AITaskProviderFailureService,
)
from .complete_provider_success import (
    AITaskProviderSuccessError,
    AITaskProviderSuccessService,
)
from .provider_execution_contract import AIProviderResponse
from .publish_pre_begin_failure import (
    AITaskPreBeginFailureError,
    AITaskPreBeginFailurePublisher,
    PublishedAITaskPreBeginFailure,
)
from .publish_suggestion_success import PublishedAITaskSuggestion
from .publish_task_failure import PublishedAITaskFailure
from .send_provider_request import (
    AITaskProviderSendError,
    AITaskProviderSendService,
)
from .task_invocation_begin import (
    AITaskInvocationBeginError,
    AITaskInvocationBeginService,
    BegunAITaskInvocation,
)
from .task_invocation_prepare import (
    AITaskInvocationPrepareError,
    AITaskInvocationPrepareService,
    PreparedAITaskInvocation,
)


class AIBusinessTaskWorkerError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_WORKER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIBusinessTaskWorkerCycle:
    state: str
    job_id: uuid.UUID | None = None
    result_id: uuid.UUID | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.state == "IDLE":
            if any(value is not None for value in (
                    self.job_id, self.result_id, self.error_code)):
                raise AIBusinessTaskWorkerError()
            return
        if type(self.job_id) is not uuid.UUID or not self.job_id.int:
            raise AIBusinessTaskWorkerError()
        if self.state == "SUCCEEDED":
            if (type(self.result_id) is not uuid.UUID or not self.result_id.int
                    or self.error_code is not None):
                raise AIBusinessTaskWorkerError()
            return
        if self.state in {"FAILED", "RECONCILIATION_PENDING"}:
            if (self.result_id is not None or type(self.error_code) is not str
                    or re.fullmatch(
                        r"[A-Z][A-Z0-9_]{0,63}", self.error_code,
                    ) is None):
                raise AIBusinessTaskWorkerError()
            return
        raise AIBusinessTaskWorkerError()


class _Leases(Protocol):
    def claim_next_ai_task(
        self, *, worker_ref: str, lease_seconds: int,
    ) -> ClaimedJob | None: ...


class AIBusinessTaskOneShotWorker:
    """Claim, prepare, begin, send and publish one exact business AI Task."""

    LEASE_SECONDS = 300
    _INVALID_RESPONSE = frozenset({
        "AI_PROVIDER_RESPONSE_INVALID",
        "AI_PROVIDER_RESPONSE_INCOMPLETE",
    })

    def __init__(
        self, *, leases: _Leases,
        preparer: AITaskInvocationPrepareService,
        beginner: AITaskInvocationBeginService,
        sender: AITaskProviderSendService,
        success: AITaskProviderSuccessService,
        failure: AITaskProviderFailureService,
        pre_begin_failure: AITaskPreBeginFailurePublisher,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                leases, preparer, beginner, sender, success, failure,
                pre_begin_failure)):
            raise ValueError("business AI Task Worker dependencies required")
        self._leases = leases
        self._preparer = preparer
        self._beginner = beginner
        self._sender = sender
        self._success = success
        self._failure = failure
        self._pre_begin_failure = pre_begin_failure
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def run_once(self, *, worker_ref: str) -> AIBusinessTaskWorkerCycle:
        try:
            JobLeaseService._validate_worker(worker_ref)
            claim = self._leases.claim_next_ai_task(
                worker_ref=worker_ref, lease_seconds=self.LEASE_SECONDS,
            )
        except JobLeaseError:
            raise AIBusinessTaskWorkerError("JOB_STORE_UNAVAILABLE") from None
        except Exception:
            raise AIBusinessTaskWorkerError("JOB_STORE_UNAVAILABLE") from None
        if claim is None:
            return AIBusinessTaskWorkerCycle("IDLE")
        self._require_claim(claim)

        prepared: PreparedAITaskInvocation | None = None
        begun: BegunAITaskInvocation | None = None
        response: AIProviderResponse | None = None
        try:
            try:
                prepared = self._preparer.prepare(
                    job_id=claim.job_id, fencing_token=claim.fencing_token,
                    worker_ref=worker_ref, now=self._now(),
                )
                if type(prepared) is not PreparedAITaskInvocation:
                    raise AITaskInvocationPrepareError()
                prepared.__post_init__()
            except AITaskInvocationPrepareError as error:
                return self._close_pre_begin(
                    claim=claim, worker_ref=worker_ref,
                    error_code=error.code, retryable=True,
                )
            except Exception:
                return self._close_pre_begin(
                    claim=claim, worker_ref=worker_ref,
                    error_code="AI_TASK_PREPARATION_FAILED", retryable=True,
                )

            try:
                begun = self._beginner.begin(
                    job_id=claim.job_id, fencing_token=claim.fencing_token,
                    worker_ref=worker_ref, now=self._now(),
                    payload_plan=prepared.payload_plan,
                )
                if type(begun) is not BegunAITaskInvocation:
                    raise AITaskInvocationBeginError()
                begun.__post_init__()
            except AITaskInvocationBeginError as error:
                if error.committed:
                    return AIBusinessTaskWorkerCycle(
                        "RECONCILIATION_PENDING", claim.job_id,
                        error_code=error.code,
                    )
                return self._close_pre_begin(
                    claim=claim, worker_ref=worker_ref,
                    error_code=error.code, retryable=True,
                )
            except Exception:
                return self._close_pre_begin(
                    claim=claim, worker_ref=worker_ref,
                    error_code="AI_TASK_INVOCATION_NOT_STARTED",
                    retryable=True,
                )

            try:
                response = self._sender.send_once(
                    prepared=prepared, begun=begun,
                    job_id=claim.job_id, fencing_token=claim.fencing_token,
                    worker_ref=worker_ref,
                )
                if type(response) is not AIProviderResponse:
                    raise AITaskProviderSendError(
                        "AI_PROVIDER_OUTCOME_UNKNOWN",
                        provider_outcome_unknown=True,
                    )
            except AITaskProviderSendError as error:
                return self._close_after_begin(
                    claim=claim, prepared=prepared, begun=begun,
                    worker_ref=worker_ref, error=error,
                )
            except Exception:
                return self._close_after_begin(
                    claim=claim, prepared=prepared, begun=begun,
                    worker_ref=worker_ref,
                    error=AITaskProviderSendError(
                        "AI_PROVIDER_OUTCOME_UNKNOWN",
                        provider_outcome_unknown=True,
                    ),
                )

            try:
                published = self._success.complete(
                    prepared=prepared, begun=begun, response=response,
                    worker_ref=worker_ref,
                )
                if type(published) is not PublishedAITaskSuggestion:
                    raise AITaskProviderSuccessError()
                published.__post_init__()
                return AIBusinessTaskWorkerCycle(
                    "SUCCEEDED", claim.job_id,
                    result_id=published.suggestion_payload_id,
                )
            except AITaskProviderSuccessError as error:
                if error.code in self._INVALID_RESPONSE:
                    return AIBusinessTaskWorkerCycle(
                        "FAILED", claim.job_id, error_code=error.code,
                    )
                return AIBusinessTaskWorkerCycle(
                    "RECONCILIATION_PENDING", claim.job_id,
                    error_code="AI_TASK_RESULT_NOT_PUBLISHED",
                )
            except Exception:
                return AIBusinessTaskWorkerCycle(
                    "RECONCILIATION_PENDING", claim.job_id,
                    error_code="AI_TASK_RESULT_NOT_PUBLISHED",
                )
        finally:
            if isinstance(response, AIProviderResponse):
                response.close()
            response = None
            begun = None
            prepared = None

    def _close_pre_begin(
        self, *, claim: ClaimedJob, worker_ref: str,
        error_code: str, retryable: bool,
    ) -> AIBusinessTaskWorkerCycle:
        try:
            result = self._pre_begin_failure.publish(
                claim=claim, worker_ref=worker_ref,
                error_code=error_code, retryable=retryable,
            )
            if type(result) is not PublishedAITaskPreBeginFailure:
                raise AITaskPreBeginFailureError()
            result.__post_init__()
            if (result.job_id != claim.job_id
                    or result.error_code != error_code
                    or result.retryable is not retryable):
                raise AITaskPreBeginFailureError()
            return AIBusinessTaskWorkerCycle(
                "FAILED", claim.job_id, error_code=result.error_code,
            )
        except AITaskPreBeginFailureError as error:
            raise AIBusinessTaskWorkerError(error.code) from None
        except Exception:
            raise AIBusinessTaskWorkerError(
                "AI_TASK_PRE_BEGIN_FAILURE_NOT_PUBLISHED",
            ) from None

    def _close_after_begin(
        self, *, claim: ClaimedJob, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, worker_ref: str,
        error: AITaskProviderSendError,
    ) -> AIBusinessTaskWorkerCycle:
        try:
            result = self._failure.complete(
                prepared=prepared, begun=begun, error=error,
                worker_ref=worker_ref,
            )
            if type(result) is not PublishedAITaskFailure:
                raise AITaskProviderFailureError()
            result.__post_init__()
            return AIBusinessTaskWorkerCycle(
                "FAILED", claim.job_id, error_code=result.error_code,
            )
        except AITaskProviderFailureError as failure:
            raise AIBusinessTaskWorkerError(failure.code) from None
        except Exception:
            raise AIBusinessTaskWorkerError(
                "AI_TASK_FAILURE_NOT_PUBLISHED",
            ) from None

    def _now(self) -> datetime:
        now = self._clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise AIBusinessTaskWorkerError("AI_TASK_WORKER_CLOCK_INVALID")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _require_claim(claim: ClaimedJob) -> None:
        try:
            trace_id = uuid.UUID(claim.trace_id)
        except (AttributeError, TypeError, ValueError):
            raise AIBusinessTaskWorkerError("JOB_STORE_UNAVAILABLE") from None
        if (type(claim) is not ClaimedJob
                or type(claim.job_id) is not uuid.UUID or not claim.job_id.int
                or claim.job_type != "AI_TASK_EXECUTE"
                or claim.scope != "PROJECT"
                or type(claim.project_id) is not uuid.UUID
                or not claim.project_id.int
                or type(claim.payload_refs) is not dict
                or type(claim.fencing_token) is not int
                or claim.fencing_token < 1
                or type(claim.attempt_no) is not int or claim.attempt_no < 1
                or not trace_id.int):
            raise AIBusinessTaskWorkerError("JOB_STORE_UNAVAILABLE")
