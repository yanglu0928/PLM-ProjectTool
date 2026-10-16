"""Atomically close one known Embedding failure without retrying it."""

from __future__ import annotations

import hmac
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    provider_route_fingerprint,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
    RAGIndexBuildClaims,
)


class RAGEmbeddingBatchFailureError(RuntimeError):
    def __init__(self, code: str = "RAG_EMBEDDING_BATCH_FAILURE_REJECTED") -> None:
        self.code = code
        super().__init__(code)


class RAGEmbeddingBatchFailurePhase(str, Enum):
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    RESPONSE_INVALID = "RESPONSE_INVALID"


@dataclass(frozen=True, slots=True)
class PublishedRAGEmbeddingBatchFailure:
    embedding_build_batch_id: uuid.UUID
    error_code: str
    cancelled_batch_count: int
    completed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.embedding_build_batch_id) is not uuid.UUID
                or not self.embedding_build_batch_id.int
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None
                or type(self.cancelled_batch_count) is not int
                or self.cancelled_batch_count < 0
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise RAGEmbeddingBatchFailureError()


class RAGEmbeddingBatchFailureRepositoryPort(Protocol):
    def publish(
        self, transaction: object, *, claim: RAGIndexBuildClaim,
        envelope: AIEmbeddingEnvelope, send: AuthorizedAIEmbeddingSend,
        error_code: str, response_ref: str | None,
    ) -> PublishedRAGEmbeddingBatchFailure | None: ...


class _JobFailureCloser(Protocol):
    def retry_or_fail(
        self, transaction: object, *, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str, error_code: str,
        retryable: bool, delay_seconds: int,
    ) -> str: ...


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class RAGEmbeddingBatchFailureService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        claims: RAGIndexBuildClaims,
        jobs: _JobFailureCloser,
        repository: RAGEmbeddingBatchFailureRepositoryPort,
        audit: AuditService,
        system_actor: _SystemActor,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, claims, jobs, repository, audit, system_actor)):
            raise ValueError("RAG Embedding failure dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._jobs = jobs
        self._repository = repository
        self._audit = audit
        self._actor = system_actor

    def publish(
        self, *, envelope: AIEmbeddingEnvelope,
        send: AuthorizedAIEmbeddingSend,
        job_id: uuid.UUID, fencing_token: int, worker_ref: str,
        phase: RAGEmbeddingBatchFailurePhase,
        response_fingerprint: bytes | None = None,
    ) -> PublishedRAGEmbeddingBatchFailure:
        error_code, response_ref = self._effective(
            phase, response_fingerprint,
        )
        try:
            if (type(envelope) is not AIEmbeddingEnvelope
                    or type(send) is not AuthorizedAIEmbeddingSend
                    or type(job_id) is not uuid.UUID or not job_id.int
                    or type(fencing_token) is not int or fencing_token < 1
                    or type(worker_ref) is not str or not worker_ref.strip()):
                raise RAGEmbeddingBatchFailureError()
            envelope.__post_init__()
            send.__post_init__()
            self._require_identity(envelope, send, job_id, fencing_token)
            actor_id = self._actor.assert_current()
            if type(actor_id) is not uuid.UUID or not actor_id.int:
                raise RAGEmbeddingBatchFailureError()
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id,
                    fencing_token=fencing_token, worker_ref=worker_ref,
                )
                if (claim.embedding_build_id != envelope.embedding_build_id
                        or claim.embedding_index_id != envelope.embedding_index_id
                        or claim.trace_id != send.proof.trace_id
                        or claim.actor_id != send.proof.actor_id
                        or claim.scope != send.proof.scope
                        or claim.project_id != send.proof.project_id):
                    raise RAGEmbeddingBatchFailureError()
                state = self._jobs.retry_or_fail(
                    transaction, job_id=job_id,
                    fencing_token=fencing_token, worker_ref=worker_ref,
                    error_code=error_code, retryable=False, delay_seconds=0,
                )
                if state != "FAILED":
                    raise RAGEmbeddingBatchFailureError()
                result = self._repository.publish(
                    transaction, claim=claim, envelope=envelope, send=send,
                    error_code=error_code, response_ref=response_ref,
                )
                if (type(result) is not PublishedRAGEmbeddingBatchFailure
                        or result.embedding_build_batch_id
                        != envelope.embedding_build_batch_id
                        or result.error_code != error_code):
                    raise RAGEmbeddingBatchFailureError()
                result.__post_init__()
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=claim.trace_id,
                    event_scope=(
                        "DEPLOYMENT" if claim.scope == "GLOBAL" else "PROJECT"
                    ),
                    target_project_id=claim.project_id,
                    actor_type="SYSTEM", actor_id=actor_id,
                    original_actor_id=claim.actor_id,
                    actor_hint_digest=None,
                    action="RAG_INDEX_BUILD_FAILED", outcome="FAILED",
                    target_owner_module="rag", target_object_type="RAG-03",
                    target_object_id=claim.embedding_index_id,
                    target_version_id=claim.embedding_build_id,
                    reason_code=error_code,
                    before_state="RUNNING", after_state="FAILED",
                ))
                if (type(event_id) is not uuid.UUID or not event_id.int
                        or self._actor.assert_current() != actor_id):
                    raise RAGEmbeddingBatchFailureError()
                transaction.commit()
            return result
        except RAGEmbeddingBatchFailureError:
            raise
        except JobLeaseError:
            raise RAGEmbeddingBatchFailureError(
                "RAG_EMBEDDING_JOB_LEASE_LOST",
            ) from None
        except Exception:
            raise RAGEmbeddingBatchFailureError() from None

    @staticmethod
    def _effective(
        phase: RAGEmbeddingBatchFailurePhase,
        response_fingerprint: bytes | None,
    ) -> tuple[str, str | None]:
        if type(phase) is not RAGEmbeddingBatchFailurePhase:
            raise RAGEmbeddingBatchFailureError()
        if phase is RAGEmbeddingBatchFailurePhase.PROVIDER_REJECTED:
            if response_fingerprint is not None:
                raise RAGEmbeddingBatchFailureError()
            return "RAG_PROVIDER_REQUEST_REJECTED", None
        if (type(response_fingerprint) is not bytes
                or len(response_fingerprint) != 32):
            raise RAGEmbeddingBatchFailureError()
        return (
            "RAG_EMBEDDING_RESPONSE_INVALID",
            "sha256:" + response_fingerprint.hex(),
        )

    @staticmethod
    def _require_identity(
        envelope: AIEmbeddingEnvelope, send: AuthorizedAIEmbeddingSend,
        job_id: uuid.UUID, fencing_token: int,
    ) -> None:
        proof, route = send.proof, send.route
        if (proof.job_id != job_id
                or proof.fencing_token != fencing_token
                or proof.embedding_build_id != envelope.embedding_build_id
                or proof.embedding_build_batch_id
                != envelope.embedding_build_batch_id
                or route.provider_model_key != envelope.provider_model_key
                or route.model_revision != envelope.model_revision
                or not hmac.compare_digest(
                    proof.route_fingerprint, provider_route_fingerprint(route))
                or not hmac.compare_digest(
                    proof.source_refs_fingerprint,
                    envelope.source_refs_fingerprint)
                or not hmac.compare_digest(
                    proof.payload_fingerprint, envelope.payload_fingerprint)
                or proof.payload_bytes != envelope.payload_bytes
                or proof.input_tokens != envelope.input_tokens):
            raise RAGEmbeddingBatchFailureError()
