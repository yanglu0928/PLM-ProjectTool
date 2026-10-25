"""Technical validation owner for one complete RAG EmbeddingIndex build."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
    RAGIndexBuildClaims,
)


class RAGEmbeddingIndexValidationError(RuntimeError):
    def __init__(self, code: str = "RAG_INDEX_VALIDATION_NOT_COMPLETED", *,
                 committed: bool = False) -> None:
        if type(committed) is not bool:
            raise ValueError("committed must be bool")
        self.code = code
        self.committed = committed
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RAGEmbeddingIndexValidationPolicy:
    policy_ref: str = "rag-index-technical-v1"
    probe_limit: int = 10
    top_k: int = 5
    minimum_recall_basis_points: int = 9500
    hnsw_ef_search: int = 200
    hnsw_iterative_scan: str = "strict_order"

    def __post_init__(self) -> None:
        if (type(self.policy_ref) is not str
                or self.policy_ref != "rag-index-technical-v1"
                or type(self.probe_limit) is not int
                or not 1 <= self.probe_limit <= 100
                or type(self.top_k) is not int or not 1 <= self.top_k <= 100
                or type(self.minimum_recall_basis_points) is not int
                or not 1 <= self.minimum_recall_basis_points <= 10000
                or self.hnsw_ef_search != 200
                or self.hnsw_iterative_scan != "strict_order"):
            raise RAGEmbeddingIndexValidationError()


@dataclass(frozen=True, slots=True)
class CompletedRAGEmbeddingIndexValidation:
    embedding_index_validation_id: uuid.UUID
    embedding_index_id: uuid.UUID
    embedding_build_id: uuid.UUID
    validation_state: str
    index_state: str
    observed_recall_basis_points: int
    completed_at: datetime

    def __post_init__(self) -> None:
        ids = (
            self.embedding_index_validation_id,
            self.embedding_index_id,
            self.embedding_build_id,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in ids)
                or self.validation_state not in {"PASSED", "FAILED"}
                or self.index_state not in {"READY", "FAILED"}
                or (self.validation_state == "PASSED")
                != (self.index_state == "READY")
                or type(self.observed_recall_basis_points) is not int
                or not 0 <= self.observed_recall_basis_points <= 10000
                or type(self.completed_at) is not datetime
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise RAGEmbeddingIndexValidationError()


class RAGEmbeddingIndexValidationRepositoryPort(Protocol):
    def validate_and_close(
        self, transaction: object, *, claim: RAGIndexBuildClaim,
        worker_ref: str, policy: RAGEmbeddingIndexValidationPolicy,
    ) -> CompletedRAGEmbeddingIndexValidation: ...


class RAGEmbeddingIndexValidationService:
    """Validate and atomically close Job/Build/Index without activating it."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: RAGIndexBuildClaims,
                 repository: RAGEmbeddingIndexValidationRepositoryPort,
                 policy: RAGEmbeddingIndexValidationPolicy | None = None) -> None:
        if any(value is None for value in (unit_of_work, claims, repository)):
            raise ValueError("RAG index validation dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository
        self._policy = policy or RAGEmbeddingIndexValidationPolicy()
        self._policy.__post_init__()

    def validate(self, *, job_id: uuid.UUID, fencing_token: int,
                 worker_ref: str) -> CompletedRAGEmbeddingIndexValidation:
        committed = False
        try:
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id,
                    fencing_token=fencing_token, worker_ref=worker_ref,
                )
                result = self._repository.validate_and_close(
                    transaction, claim=claim, worker_ref=worker_ref,
                    policy=self._policy,
                )
                if (type(result) is not CompletedRAGEmbeddingIndexValidation
                        or result.embedding_index_id != claim.embedding_index_id
                        or result.embedding_build_id != claim.embedding_build_id):
                    raise RAGEmbeddingIndexValidationError()
                result.__post_init__()
                transaction.commit()
                committed = True
            return result
        except RAGEmbeddingIndexValidationError as error:
            if committed and not error.committed:
                raise RAGEmbeddingIndexValidationError(
                    error.code, committed=True,
                ) from None
            raise
        except JobLeaseError:
            raise RAGEmbeddingIndexValidationError(
                committed=committed,
            ) from None
        except Exception:
            raise RAGEmbeddingIndexValidationError(
                committed=committed,
            ) from None
