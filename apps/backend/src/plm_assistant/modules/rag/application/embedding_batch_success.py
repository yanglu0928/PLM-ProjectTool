"""Publish one proven Embedding response under the current RAG lease."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.embedding_response_contract import (
    ParsedAIEmbeddingResponse,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    provider_route_fingerprint,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
    RAGIndexBuildClaims,
)


class RAGEmbeddingBatchSuccessError(RuntimeError):
    def __init__(self, code: str = "RAG_EMBEDDING_BATCH_SUCCESS_REJECTED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PublishedRAGEmbeddingBatch:
    embedding_build_batch_id: uuid.UUID
    embedding_record_ids: tuple[uuid.UUID, ...]
    provider_request_ref: str
    completed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.embedding_build_batch_id) is not uuid.UUID
                or not self.embedding_build_batch_id.int
                or type(self.embedding_record_ids) is not tuple
                or not self.embedding_record_ids
                or any(type(value) is not uuid.UUID or not value.int
                       for value in self.embedding_record_ids)
                or len(set(self.embedding_record_ids))
                != len(self.embedding_record_ids)
                or type(self.provider_request_ref) is not str
                or not self.provider_request_ref
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise RAGEmbeddingBatchSuccessError()


class RAGEmbeddingBatchSuccessRepositoryPort(Protocol):
    def publish(self, transaction: object, *, claim: RAGIndexBuildClaim,
                envelope: AIEmbeddingEnvelope,
                send: AuthorizedAIEmbeddingSend,
                parsed: ParsedAIEmbeddingResponse
                ) -> PublishedRAGEmbeddingBatch | None: ...


class RAGEmbeddingBatchSuccessService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: RAGIndexBuildClaims,
                 repository: RAGEmbeddingBatchSuccessRepositoryPort) -> None:
        if any(value is None for value in (unit_of_work, claims, repository)):
            raise ValueError("RAG Embedding success dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository

    def publish(self, *, envelope: AIEmbeddingEnvelope,
                send: AuthorizedAIEmbeddingSend,
                parsed: ParsedAIEmbeddingResponse,
                job_id: uuid.UUID, fencing_token: int,
                worker_ref: str) -> PublishedRAGEmbeddingBatch:
        try:
            if (type(envelope) is not AIEmbeddingEnvelope
                    or type(send) is not AuthorizedAIEmbeddingSend
                    or type(parsed) is not ParsedAIEmbeddingResponse
                    or type(job_id) is not uuid.UUID or not job_id.int
                    or type(fencing_token) is not int or fencing_token < 1
                    or type(worker_ref) is not str or not worker_ref.strip()):
                raise RAGEmbeddingBatchSuccessError()
            envelope.__post_init__()
            send.__post_init__()
            parsed.__post_init__()
            self._require_identity(envelope, send, parsed, job_id, fencing_token)
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
                    raise RAGEmbeddingBatchSuccessError()
                result = self._repository.publish(
                    transaction, claim=claim, envelope=envelope,
                    send=send, parsed=parsed,
                )
                if type(result) is not PublishedRAGEmbeddingBatch:
                    raise RAGEmbeddingBatchSuccessError()
                result.__post_init__()
                if (result.embedding_build_batch_id
                        != envelope.embedding_build_batch_id
                        or len(result.embedding_record_ids)
                        != envelope.record_count
                        or result.provider_request_ref
                        != parsed.provider_request_ref):
                    raise RAGEmbeddingBatchSuccessError()
                transaction.commit()
            return result
        except RAGEmbeddingBatchSuccessError:
            raise
        except JobLeaseError:
            raise RAGEmbeddingBatchSuccessError() from None
        except Exception:
            raise RAGEmbeddingBatchSuccessError() from None

    @staticmethod
    def _require_identity(envelope: AIEmbeddingEnvelope,
                          send: AuthorizedAIEmbeddingSend,
                          parsed: ParsedAIEmbeddingResponse,
                          job_id: uuid.UUID, fencing_token: int) -> None:
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
                or not hmac.compare_digest(
                    parsed.route_fingerprint, proof.route_fingerprint)
                or not hmac.compare_digest(
                    parsed.payload_fingerprint, envelope.payload_fingerprint)
                or not hmac.compare_digest(
                    parsed.source_refs_fingerprint,
                    envelope.source_refs_fingerprint)
                or proof.payload_bytes != envelope.payload_bytes
                or proof.input_tokens != envelope.input_tokens
                or len(parsed.vectors) != envelope.record_count
                or any(len(vector.values) != envelope.embedding_dimension
                       for vector in parsed.vectors)):
            raise RAGEmbeddingBatchSuccessError()
