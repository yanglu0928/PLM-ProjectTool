"""Classify one Provider send failure and atomically close its AI execution."""

from __future__ import annotations

from .publish_task_failure import (
    AITaskFailurePhase,
    AITaskFailurePublicationError,
    AITaskFailurePublisher,
    PublishedAITaskFailure,
)
from .send_provider_request import AITaskProviderSendError
from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


_EXPLICIT_RETRYABLE_PRE_SEND = frozenset({
    "AI_PROVIDER_SEND_UNAVAILABLE",
    "AI_PROVIDER_SECRET_UNAVAILABLE",
    "AI_PROVIDER_DESTINATION_UNAVAILABLE",
})


class AITaskProviderFailureError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_FAILURE_NOT_PUBLISHED") -> None:
        self.code = code
        super().__init__(code)


class AITaskProviderFailureService:
    def __init__(self, *, publisher: AITaskFailurePublisher) -> None:
        if publisher is None:
            raise ValueError("AI Provider failure publisher required")
        self._publisher = publisher

    def complete(
        self, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, error: AITaskProviderSendError,
        worker_ref: str,
    ) -> PublishedAITaskFailure:
        if type(error) is not AITaskProviderSendError:
            raise AITaskProviderFailureError()
        phase = (
            AITaskFailurePhase.PROVIDER_OUTCOME_UNKNOWN
            if error.provider_outcome_unknown
            else AITaskFailurePhase.PRE_SEND
        )
        try:
            return self._publisher.publish(
                prepared=prepared, begun=begun, worker_ref=worker_ref,
                phase=phase, error_code=error.code,
                retryable=(
                    phase is AITaskFailurePhase.PRE_SEND
                    and error.code in _EXPLICIT_RETRYABLE_PRE_SEND
                ),
            )
        except AITaskFailurePublicationError as failure:
            raise AITaskProviderFailureError(failure.code) from None
