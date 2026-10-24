"""Atomically start one leased RAG embedding build generation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
    RAGIndexBuildClaims,
)


class RAGEmbeddingBuildBeginError(RuntimeError):
    def __init__(self, code: str = "RAG_INDEX_BUILD_NOT_STARTED", *,
                 committed: bool = False) -> None:
        if type(committed) is not bool:
            raise ValueError("committed must be bool")
        self.code = code
        self.committed = committed
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BegunRAGEmbeddingBuild:
    embedding_build_id: uuid.UUID
    embedding_index_id: uuid.UUID
    claim: RAGIndexBuildClaim

    def __post_init__(self) -> None:
        if (type(self.embedding_build_id) is not uuid.UUID
                or not self.embedding_build_id.int
                or type(self.embedding_index_id) is not uuid.UUID
                or not self.embedding_index_id.int
                or type(self.claim) is not RAGIndexBuildClaim
                or self.embedding_build_id != self.claim.embedding_build_id
                or self.embedding_index_id != self.claim.embedding_index_id):
            raise RAGEmbeddingBuildBeginError()
        self.claim.__post_init__()


class RAGEmbeddingBuildBeginRepositoryPort(Protocol):
    def begin(self, transaction: object, *, claim: RAGIndexBuildClaim) -> None: ...


class RAGEmbeddingBuildBeginService:
    """Current lease proof and both state transitions share one transaction."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: RAGIndexBuildClaims,
                 repository: RAGEmbeddingBuildBeginRepositoryPort) -> None:
        if any(value is None for value in (unit_of_work, claims, repository)):
            raise ValueError("RAG embedding build begin dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository

    def begin(self, *, job_id: uuid.UUID, fencing_token: int,
              worker_ref: str) -> BegunRAGEmbeddingBuild:
        committed = False
        try:
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                self._repository.begin(transaction, claim=claim)
                result = BegunRAGEmbeddingBuild(
                    claim.embedding_build_id, claim.embedding_index_id, claim,
                )
                transaction.commit()
                committed = True
            return result
        except RAGEmbeddingBuildBeginError as error:
            if committed and not error.committed:
                raise RAGEmbeddingBuildBeginError(
                    error.code, committed=True,
                ) from None
            raise
        except JobLeaseError:
            raise RAGEmbeddingBuildBeginError(committed=committed) from None
        except Exception:
            raise RAGEmbeddingBuildBeginError(committed=committed) from None
