"""Bounded immutable PROJECT FTS candidate plan; persistence belongs to A05."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    PreparedRAGRetrieval,
    RAGRetrievalPreparationError,
)


@dataclass(frozen=True, slots=True)
class ProjectFTSCandidate:
    candidate_ordinal: int
    embedding_index_id: uuid.UUID
    embedding_model_ref: uuid.UUID
    chunk_id: uuid.UUID
    document_version_ref: uuid.UUID
    parse_result_ref: uuid.UUID
    source_type: str
    source_locator: dict = field(repr=False)
    retrieval_channel: str
    raw_score_micros: int
    authorization_snapshot_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        required = (
            self.embedding_index_id, self.embedding_model_ref, self.chunk_id,
            self.document_version_ref, self.parse_result_ref,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in required)
                or type(self.candidate_ordinal) is not int
                or not 0 <= self.candidate_ordinal < 400
                or self.source_type not in {
                    "CONTRACTUAL", "PROJECT_RECORD", "STANDARD_CAPABILITY",
                    "REFERENCE_MATERIAL", "TEMPLATE", "GENERATED_ARTIFACT", "OTHER",
                }
                or type(self.source_locator) is not dict
                or type(self.source_locator.get("locator_type")) is not str
                or self.retrieval_channel != "FTS"
                or type(self.raw_score_micros) is not int
                or not 0 <= self.raw_score_micros <= 1_000_000_000
                or type(self.authorization_snapshot_fingerprint) is not bytes
                or len(self.authorization_snapshot_fingerprint) != 32):
            raise RAGRetrievalPreparationError("RAG_FTS_CANDIDATE_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class ProjectFTSCandidatePlan:
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    project_index_ref: uuid.UUID
    query_fingerprint: bytes = field(repr=False)
    candidates: tuple[ProjectFTSCandidate, ...]

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.retrieval_run_id, self.project_id, self.project_index_ref))
                or type(self.query_fingerprint) is not bytes
                or len(self.query_fingerprint) != 32
                or type(self.candidates) is not tuple
                or len(self.candidates) > 400
                or any(type(item) is not ProjectFTSCandidate
                       for item in self.candidates)
                or tuple(item.candidate_ordinal for item in self.candidates)
                != tuple(range(len(self.candidates)))
                or len({item.chunk_id for item in self.candidates})
                != len(self.candidates)):
            raise RAGRetrievalPreparationError("RAG_FTS_CANDIDATE_UNAVAILABLE")


class _Repository(Protocol):
    def project_fts(self, transaction: object, *, prepared: PreparedRAGRetrieval
                    ) -> tuple[ProjectFTSCandidate, ...]: ...


class ProjectFTSCandidatePlanner:
    def __init__(self, repository: _Repository) -> None:
        if repository is None:
            raise ValueError("PROJECT FTS repository required")
        self._repository = repository

    def plan(self, transaction: object, *, prepared: PreparedRAGRetrieval
             ) -> ProjectFTSCandidatePlan:
        try:
            if type(prepared) is not PreparedRAGRetrieval:
                raise RAGRetrievalPreparationError("RAG_FTS_CANDIDATE_UNAVAILABLE")
            prepared.__post_init__()
            candidates = self._repository.project_fts(
                transaction, prepared=prepared,
            )
            plan = ProjectFTSCandidatePlan(
                prepared.retrieval_run_id, prepared.project_id,
                prepared.project_index_ref, prepared.query_fingerprint,
                candidates,
            )
            plan.__post_init__()
            for candidate in candidates:
                candidate.__post_init__()
                if (candidate.embedding_index_id != prepared.project_index_ref
                        or candidate.embedding_model_ref != prepared.project_model_ref
                        or not candidate.authorization_snapshot_fingerprint
                        == prepared.authorization_snapshot_fingerprint):
                    raise RAGRetrievalPreparationError(
                        "RAG_FTS_CANDIDATE_UNAVAILABLE")
            return plan
        except RAGRetrievalPreparationError:
            raise
        except Exception:
            raise RAGRetrievalPreparationError(
                "RAG_FTS_CANDIDATE_UNAVAILABLE") from None
