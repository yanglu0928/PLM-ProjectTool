"""Durable pre-network fence for one authorized RAG embedding batch."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
    RAGIndexBuildClaims,
)


class RAGEmbeddingBatchSendFenceError(RuntimeError):
    def __init__(self, code: str = "RAG_EMBEDDING_BATCH_SEND_NOT_AUTHORIZED",
                 *, committed: bool = False) -> None:
        if type(committed) is not bool:
            raise ValueError("committed must be bool")
        self.code = code
        self.committed = committed
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RAGEmbeddingBatchPayloadProof:
    embedding_build_id: uuid.UUID
    embedding_index_id: uuid.UUID
    batch_ordinal: int
    source_first_ordinal: int
    source_record_count: int
    source_batch_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    payload_bytes: int
    input_tokens: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.embedding_build_id, self.embedding_index_id))
                or type(self.batch_ordinal) is not int
                or not 1 <= self.batch_ordinal <= 100_000
                or type(self.source_first_ordinal) is not int
                or not 1 <= self.source_first_ordinal <= 1_000_000_000
                or type(self.source_record_count) is not int
                or not 1 <= self.source_record_count <= 1_000
                or type(self.source_batch_fingerprint) is not bytes
                or len(self.source_batch_fingerprint) != 32
                or type(self.payload_fingerprint) is not bytes
                or len(self.payload_fingerprint) != 32
                or type(self.payload_bytes) is not int
                or not 1 <= self.payload_bytes <= 100_000_000
                or type(self.input_tokens) is not int
                or not 1 <= self.input_tokens <= 1_048_576):
            raise RAGEmbeddingBatchSendFenceError()


@dataclass(frozen=True, slots=True)
class RAGEmbeddingBatchSendMaterial:
    embedding_build_batch_id: uuid.UUID
    egress_authorization_ref: uuid.UUID
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    secret_ref: uuid.UUID
    provider_kind: str
    endpoint_policy_ref: str
    data_region: str
    egress_class: str
    provider_model_key: str
    model_revision: str
    embedding_dimension: int
    valid_until: datetime
    lock_version: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.embedding_build_batch_id, self.egress_authorization_ref,
                self.ai_provider_id, self.provider_config_version_id,
                self.ai_model_id, self.secret_ref))
                or any(type(value) is not str or not value for value in (
                    self.provider_kind, self.endpoint_policy_ref, self.data_region,
                    self.egress_class, self.provider_model_key, self.model_revision))
                or self.embedding_dimension not in {768, 1024}
                or not isinstance(self.valid_until, datetime)
                or self.valid_until.tzinfo is None
                or self.valid_until.utcoffset() is None
                or type(self.lock_version) is not int or self.lock_version < 1):
            raise RAGEmbeddingBatchSendFenceError()


@dataclass(frozen=True, slots=True)
class FencedRAGEmbeddingBatch:
    proof: RAGEmbeddingBatchPayloadProof
    claim: RAGIndexBuildClaim
    material: RAGEmbeddingBatchSendMaterial
    fenced_at: datetime

    def __post_init__(self) -> None:
        if (type(self.proof) is not RAGEmbeddingBatchPayloadProof
                or type(self.claim) is not RAGIndexBuildClaim
                or type(self.material) is not RAGEmbeddingBatchSendMaterial
                or not isinstance(self.fenced_at, datetime)
                or self.fenced_at.tzinfo is None
                or self.fenced_at.utcoffset() is None):
            raise RAGEmbeddingBatchSendFenceError()
        self.proof.__post_init__()
        self.claim.__post_init__()
        self.material.__post_init__()


class RAGEmbeddingBatchSendFenceRepositoryPort(Protocol):
    def mark_running(
        self, transaction: object, *, claim: RAGIndexBuildClaim,
        proof: RAGEmbeddingBatchPayloadProof, started_at: datetime,
    ) -> RAGEmbeddingBatchSendMaterial | None: ...


class RAGEmbeddingBatchSendFenceService:
    """Commit a batch send boundary; this receipt alone cannot call a Provider."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: RAGIndexBuildClaims,
                 repository: RAGEmbeddingBatchSendFenceRepositoryPort) -> None:
        if any(value is None for value in (unit_of_work, claims, repository)):
            raise ValueError("RAG embedding batch send fence dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository

    def fence(self, *, proof: RAGEmbeddingBatchPayloadProof,
              job_id: uuid.UUID, fencing_token: int,
              worker_ref: str) -> FencedRAGEmbeddingBatch:
        committed = False
        try:
            if (type(proof) is not RAGEmbeddingBatchPayloadProof
                    or type(job_id) is not uuid.UUID or not job_id.int
                    or type(fencing_token) is not int or fencing_token < 1
                    or type(worker_ref) is not str or not worker_ref.strip()):
                raise RAGEmbeddingBatchSendFenceError()
            proof.__post_init__()
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                self._require_claim(
                    proof, claim, job_id=job_id,
                    fencing_token=fencing_token,
                )
                started_at = claim.observed_at
                material = self._repository.mark_running(
                    transaction, claim=claim, proof=proof,
                    started_at=started_at,
                )
                if type(material) is not RAGEmbeddingBatchSendMaterial:
                    raise RAGEmbeddingBatchSendFenceError()
                material.__post_init__()
                if started_at >= material.valid_until:
                    raise RAGEmbeddingBatchSendFenceError()
                result = FencedRAGEmbeddingBatch(
                    proof, claim, material, started_at,
                )
                transaction.commit()
                committed = True
            return result
        except RAGEmbeddingBatchSendFenceError as error:
            if committed and not error.committed:
                raise RAGEmbeddingBatchSendFenceError(
                    error.code, committed=True,
                ) from None
            raise
        except JobLeaseError:
            raise RAGEmbeddingBatchSendFenceError(committed=committed) from None
        except Exception:
            raise RAGEmbeddingBatchSendFenceError(committed=committed) from None

    @staticmethod
    def _require_claim(proof: RAGEmbeddingBatchPayloadProof,
                       claim: RAGIndexBuildClaim, *, job_id: uuid.UUID,
                       fencing_token: int) -> None:
        if (claim.job_id != job_id
                or claim.fencing_token != fencing_token
                or proof.embedding_build_id != claim.embedding_build_id
                or proof.embedding_index_id != claim.embedding_index_id
                or claim.fencing_token != 1 or claim.attempt_no != 1
                or claim.observed_at >= claim.lease_expires_at):
            raise RAGEmbeddingBatchSendFenceError()
