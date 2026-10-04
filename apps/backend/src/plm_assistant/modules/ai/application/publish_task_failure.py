"""Atomically close one current AI execution failure without automatic resend."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint

from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


class AITaskFailurePublicationError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_FAILURE_NOT_PUBLISHED") -> None:
        self.code = code
        super().__init__(code)


class AITaskFailurePhase(str, Enum):
    PRE_SEND = "PRE_SEND"
    PROVIDER_OUTCOME_UNKNOWN = "PROVIDER_OUTCOME_UNKNOWN"
    RESPONSE_INVALID = "RESPONSE_INVALID"


@dataclass(frozen=True, slots=True)
class PublishedAITaskFailure:
    error_code: str
    retryable: bool
    phase: AITaskFailurePhase
    completed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.error_code) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None
                or type(self.retryable) is not bool
                or type(self.phase) is not AITaskFailurePhase
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise AITaskFailurePublicationError()


class AITaskFailureStorePort(Protocol):
    def publish(
        self, transaction: object, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, phase: AITaskFailurePhase,
        error_code: str, retryable: bool,
        response_fingerprint: bytes | None,
    ) -> PublishedAITaskFailure: ...


class _JobFailureCloser(Protocol):
    def retry_or_fail(
        self, transaction: object, *, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str, error_code: str,
        retryable: bool, delay_seconds: int,
    ) -> str: ...


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class AITaskFailurePublisher:
    """Close Job/Invocation/Task/Audit together; Jobs never enters RETRY_WAIT."""

    def __init__(
        self, *, unit_of_work: Callable[[], object], store: AITaskFailureStorePort,
        jobs: _JobFailureCloser, audit: AuditService, system_actor: _SystemActor,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, store, jobs, audit, system_actor)):
            raise ValueError("AI Task failure publication dependencies required")
        self._uow = unit_of_work
        self._store = store
        self._jobs = jobs
        self._audit = audit
        self._actor = system_actor

    def publish(
        self, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, worker_ref: str,
        phase: AITaskFailurePhase, error_code: str,
        retryable: bool, response_fingerprint: bytes | None = None,
    ) -> PublishedAITaskFailure:
        if (type(prepared) is not PreparedAITaskInvocation
                or type(begun) is not BegunAITaskInvocation
                or type(worker_ref) is not str or not worker_ref.strip()
                or type(phase) is not AITaskFailurePhase
                or type(error_code) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", error_code) is None
                or type(retryable) is not bool
                or (response_fingerprint is not None
                    and (type(response_fingerprint) is not bytes
                         or len(response_fingerprint) != 32))):
            raise AITaskFailurePublicationError()
        try:
            prepared.__post_init__()
            begun.__post_init__()
            grant = prepared.grant
            if begun.grant != grant:
                raise AITaskFailurePublicationError()
            validate_checkpoint(
                job_id=grant.job_id, fencing_token=grant.fencing_token,
                worker_ref=worker_ref,
            )
            effective_code, effective_retryable = self._effective(
                phase, error_code, retryable, response_fingerprint,
            )
            actor_id = self._actor.assert_current()
            if type(actor_id) is not uuid.UUID or not actor_id.int:
                raise AITaskFailurePublicationError()
            with self._uow() as transaction:
                state = self._jobs.retry_or_fail(
                    transaction, job_id=grant.job_id,
                    fencing_token=grant.fencing_token,
                    worker_ref=worker_ref, error_code=effective_code,
                    retryable=False, delay_seconds=0,
                )
                if state != "FAILED":
                    raise AITaskFailurePublicationError()
                result = self._store.publish(
                    transaction, prepared=prepared, begun=begun, phase=phase,
                    error_code=effective_code,
                    retryable=effective_retryable,
                    response_fingerprint=response_fingerprint,
                )
                if (type(result) is not PublishedAITaskFailure
                        or result.error_code != effective_code
                        or result.retryable is not effective_retryable
                        or result.phase is not phase):
                    raise AITaskFailurePublicationError()
                result.__post_init__()
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=grant.trace_id,
                    event_scope="PROJECT",
                    target_project_id=grant.project_id,
                    actor_type="SYSTEM", actor_id=actor_id,
                    original_actor_id=grant.requested_by,
                    actor_hint_digest=None,
                    action="AI_TASK_EXECUTION_FAILED", outcome="FAILED",
                    target_owner_module="ai", target_object_type="AI-04",
                    target_object_id=grant.ai_task_id,
                    target_version_id=begun.ai_invocation_id,
                    before_state="RUNNING", after_state="FAILED",
                ))
                if (type(event_id) is not uuid.UUID or not event_id.int
                        or self._actor.assert_current() != actor_id):
                    raise AITaskFailurePublicationError()
                transaction.commit()
            return result
        except AITaskFailurePublicationError:
            raise
        except JobLeaseError:
            raise AITaskFailurePublicationError(
                "AI_TASK_JOB_LEASE_LOST",
            ) from None
        except Exception:
            raise AITaskFailurePublicationError() from None

    @staticmethod
    def _effective(
        phase: AITaskFailurePhase, error_code: str, retryable: bool,
        response_fingerprint: bytes | None,
    ) -> tuple[str, bool]:
        if phase is AITaskFailurePhase.PROVIDER_OUTCOME_UNKNOWN:
            if response_fingerprint is not None:
                raise AITaskFailurePublicationError()
            return "AI_PROVIDER_OUTCOME_UNKNOWN", False
        if phase is AITaskFailurePhase.RESPONSE_INVALID:
            if (error_code not in {
                    "AI_PROVIDER_RESPONSE_INVALID",
                    "AI_PROVIDER_RESPONSE_INCOMPLETE",
                } or response_fingerprint is None or retryable):
                raise AITaskFailurePublicationError()
            return error_code, False
        if response_fingerprint is not None:
            raise AITaskFailurePublicationError()
        return error_code, retryable
