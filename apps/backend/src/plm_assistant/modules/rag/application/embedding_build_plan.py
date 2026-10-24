"""Create one sealed, per-batch-authorized embedding build plan."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


class RAGEmbeddingBuildPlanError(RuntimeError):
    def __init__(self, code: str = "RAG_INDEX_BUILD_NOT_PLANNED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RAGEmbeddingBatchPlan:
    batch_ordinal: int
    source_first_ordinal: int
    source_record_count: int
    source_batch_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    payload_bytes: int
    input_tokens: int
    egress_authorization_ref: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.batch_ordinal) is not int
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
                or not 1 <= self.input_tokens <= 1_048_576
                or type(self.egress_authorization_ref) is not uuid.UUID
                or not self.egress_authorization_ref.int):
            raise RAGEmbeddingBuildPlanError()


@dataclass(frozen=True, slots=True)
class RAGEmbeddingBuildPlanRequest:
    embedding_index_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    batches: tuple[RAGEmbeddingBatchPlan, ...]

    def __post_init__(self) -> None:
        if (type(self.embedding_index_id) is not uuid.UUID
                or not self.embedding_index_id.int
                or type(self.actor_id) is not uuid.UUID or not self.actor_id.int
                or type(self.trace_id) is not uuid.UUID or not self.trace_id.int
                or type(self.batches) is not tuple
                or not 1 <= len(self.batches) <= 100_000):
            raise RAGEmbeddingBuildPlanError()
        expected_source = 1
        authorizations: set[uuid.UUID] = set()
        for expected_batch, batch in enumerate(self.batches, 1):
            if type(batch) is not RAGEmbeddingBatchPlan:
                raise RAGEmbeddingBuildPlanError()
            batch.__post_init__()
            if (batch.batch_ordinal != expected_batch
                    or batch.source_first_ordinal != expected_source
                    or batch.egress_authorization_ref in authorizations):
                raise RAGEmbeddingBuildPlanError()
            expected_source += batch.source_record_count
            authorizations.add(batch.egress_authorization_ref)


@dataclass(frozen=True, slots=True)
class PlannedRAGEmbeddingBuild:
    embedding_build_id: uuid.UUID
    embedding_index_id: uuid.UUID
    job_id: uuid.UUID
    build_generation: int = 1

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.embedding_build_id, self.embedding_index_id, self.job_id))
                or self.build_generation != 1):
            raise RAGEmbeddingBuildPlanError()


class RAGEmbeddingBuildPlanRepositoryPort(Protocol):
    def create(self, transaction: object, *, request: RAGEmbeddingBuildPlanRequest,
               embedding_build_id: uuid.UUID, job_id: uuid.UUID
               ) -> PlannedRAGEmbeddingBuild: ...


class RAGEmbeddingBuildPlanner:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: RAGEmbeddingBuildPlanRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("RAG embedding build planner dependencies required")
        self._uow = unit_of_work
        self._repository = repository

    def create(self, request: RAGEmbeddingBuildPlanRequest) -> PlannedRAGEmbeddingBuild:
        if type(request) is not RAGEmbeddingBuildPlanRequest:
            raise RAGEmbeddingBuildPlanError()
        request.__post_init__()
        build_id, job_id = uuid.uuid4(), uuid.uuid4()
        try:
            with self._uow() as transaction:
                result = self._repository.create(
                    transaction, request=request,
                    embedding_build_id=build_id, job_id=job_id,
                )
                if (type(result) is not PlannedRAGEmbeddingBuild
                        or result.embedding_build_id != build_id
                        or result.embedding_index_id != request.embedding_index_id
                        or result.job_id != job_id):
                    raise RAGEmbeddingBuildPlanError()
                result.__post_init__()
                transaction.commit()
                return result
        except RAGEmbeddingBuildPlanError:
            raise
        except Exception:
            raise RAGEmbeddingBuildPlanError() from None
