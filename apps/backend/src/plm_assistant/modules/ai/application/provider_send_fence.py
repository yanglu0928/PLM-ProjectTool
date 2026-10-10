"""Durable PENDING-to-RUNNING fence immediately before Provider I/O."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError

from .provider_execution_contract import (
    AIProviderExecutionError,
    require_provider_send,
)
from .provider_execution_pre_send import AuthorizedAIProviderSend
from .task_execution_grant import execution_grant_fingerprint
from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


class AITaskProviderSendFenceError(RuntimeError):
    def __init__(self, code: str = "AI_PROVIDER_SEND_NOT_AUTHORIZED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class FencedAITaskProviderSend:
    ai_invocation_id: uuid.UUID
    invocation_lock_version: int
    fenced_at: datetime

    def __post_init__(self) -> None:
        if (type(self.ai_invocation_id) is not uuid.UUID
                or not self.ai_invocation_id.int
                or type(self.invocation_lock_version) is not int
                or self.invocation_lock_version < 1
                or not isinstance(self.fenced_at, datetime)
                or self.fenced_at.tzinfo is None
                or self.fenced_at.utcoffset() is None):
            raise AITaskProviderSendFenceError()


class AITaskProviderSendFenceRepositoryPort(Protocol):
    def mark_running(
        self, transaction: object, *, claim: AITaskExecutionClaim,
        prepared: PreparedAITaskInvocation, begun: BegunAITaskInvocation,
        send: AuthorizedAIProviderSend, started_at: datetime,
    ) -> int | None: ...


class AITaskProviderSendFenceService:
    """Commit one current execution generation as RUNNING before network I/O."""

    def __init__(
        self, *, unit_of_work: Callable[[], object],
        claims: AITaskExecutionClaims,
        repository: AITaskProviderSendFenceRepositoryPort,
    ) -> None:
        if any(value is None for value in (unit_of_work, claims, repository)):
            raise ValueError("AI Provider send fence dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository

    def fence(
        self, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, send: AuthorizedAIProviderSend,
        job_id: uuid.UUID, fencing_token: int, worker_ref: str,
        now: datetime,
    ) -> FencedAITaskProviderSend:
        if (type(prepared) is not PreparedAITaskInvocation
                or type(begun) is not BegunAITaskInvocation
                or type(send) is not AuthorizedAIProviderSend
                or type(job_id) is not uuid.UUID or not job_id.int
                or type(fencing_token) is not int or fencing_token < 1
                or type(worker_ref) is not str or not worker_ref.strip()
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise AITaskProviderSendFenceError()
        now = now.astimezone(timezone.utc)
        try:
            prepared.__post_init__()
            begun.__post_init__()
            send.__post_init__()
            self._require_identity(prepared, begun, send, job_id, fencing_token)
            require_provider_send(
                send.proof, send.route, prepared.envelope, now=now,
            )
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                self._require_claim(prepared, claim, send, now)
                started_at = claim.observed_at.astimezone(timezone.utc)
                version = self._repository.mark_running(
                    transaction, claim=claim, prepared=prepared, begun=begun,
                    send=send, started_at=started_at,
                )
                if type(version) is not int or version < 1:
                    raise AITaskProviderSendFenceError()
                result = FencedAITaskProviderSend(
                    begun.ai_invocation_id, version, started_at,
                )
                transaction.commit()
            return result
        except AITaskProviderSendFenceError:
            raise
        except (AIProviderExecutionError, JobLeaseError):
            raise AITaskProviderSendFenceError() from None
        except Exception:
            raise AITaskProviderSendFenceError() from None

    @staticmethod
    def _require_identity(
        prepared: PreparedAITaskInvocation, begun: BegunAITaskInvocation,
        send: AuthorizedAIProviderSend, job_id: uuid.UUID,
        fencing_token: int,
    ) -> None:
        grant, proof = prepared.grant, send.proof
        grant_fingerprint = execution_grant_fingerprint(grant)
        if (begun.grant != grant
                or proof.ai_task_id != grant.ai_task_id
                or proof.ai_invocation_id != begun.ai_invocation_id
                or proof.job_id != job_id or job_id != grant.job_id
                or proof.attempt_no != grant.attempt_no
                or proof.fencing_token != fencing_token
                or fencing_token != grant.fencing_token
                or proof.content_plan_id != grant.content_plan_id
                or proof.authorization_ref != grant.authorization_ref
                or not hmac.compare_digest(
                    proof.grant_fingerprint, grant_fingerprint)
                or not hmac.compare_digest(
                    proof.payload_fingerprint,
                    prepared.envelope.payload_fingerprint)):
            raise AITaskProviderSendFenceError()

    @staticmethod
    def _require_claim(
        prepared: PreparedAITaskInvocation, claim: AITaskExecutionClaim,
        send: AuthorizedAIProviderSend, now: datetime,
    ) -> None:
        grant = prepared.grant
        if (claim.ai_task_id != grant.ai_task_id
                or claim.project_id != grant.project_id
                or claim.job_id != grant.job_id
                or claim.actor_id != grant.requested_by
                or claim.trace_id != grant.trace_id
                or claim.egress_authorization_ref != grant.authorization_ref
                or not hmac.compare_digest(
                    claim.input_fingerprint, grant.source_refs_fingerprint)
                or claim.attempt_no != grant.attempt_no
                or claim.fencing_token != grant.fencing_token
                or claim.max_attempts != grant.max_retry_attempts
                or claim.observed_at >= claim.lease_expires_at
                or now >= send.proof.valid_until
                or claim.observed_at >= send.proof.valid_until):
            raise AITaskProviderSendFenceError()
