from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from poc04_gateway import AIError

from .reranker import RerankerError


class RetrievalUnavailable(RuntimeError):
    """Raised when retrieval storage cannot serve a request."""


@dataclass(frozen=True, slots=True)
class RetrievedItem:
    candidate_id: str
    score: float
    content: str


class RetrievalPort(Protocol):
    def search(self, project_id: str, query: str) -> Sequence[RetrievedItem]: ...


class RerankPort(Protocol):
    def rerank(self, query: str, candidates: Sequence[RetrievedItem]) -> Sequence[RetrievedItem]: ...


class AnswerPort(Protocol):
    def answer(
        self, project_id: str, query: str, candidates: Sequence[RetrievedItem]
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class RagExecutionResult:
    status: str
    user_message_code: str
    retryable: bool
    ai_called: bool
    degraded_components: tuple[str, ...] = ()
    citation_ids: tuple[str, ...] = ()
    error_code: str | None = None

    def to_sanitized_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "user_message_code": self.user_message_code,
            "retryable": self.retryable,
            "ai_called": self.ai_called,
            "degraded_components": list(self.degraded_components),
            "citation_ids": list(self.citation_ids),
            "error_code": self.error_code,
            "query_text_committed": False,
            "candidate_content_committed": False,
            "ai_output_committed": False,
            "exception_message_committed": False,
        }


class SafeRagExecutor:
    def __init__(
        self,
        retrieval: RetrievalPort,
        reranker: RerankPort,
        answer_service: AnswerPort,
        *,
        minimum_reliable_score: float = 0.5,
    ) -> None:
        if not 0 <= minimum_reliable_score <= 1:
            raise ValueError("minimum_reliable_score must be between 0 and 1")
        self._retrieval = retrieval
        self._reranker = reranker
        self._answer_service = answer_service
        self._minimum_reliable_score = minimum_reliable_score

    def execute(self, *, project_id: str, query: str) -> RagExecutionResult:
        if not project_id.strip() or not query.strip():
            raise ValueError("project_id and query are required")
        try:
            candidates = tuple(self._retrieval.search(project_id.strip(), query.strip()))
        except RetrievalUnavailable:
            return RagExecutionResult(
                status="RETRIEVAL_UNAVAILABLE",
                user_message_code="RAG_RETRY_LATER",
                retryable=True,
                ai_called=False,
                error_code="RETRIEVAL_UNAVAILABLE",
            )
        if not candidates or max(item.score for item in candidates) < self._minimum_reliable_score:
            return RagExecutionResult(
                status="NO_RELIABLE_MATCH",
                user_message_code="RAG_NO_RELIABLE_MATCH",
                retryable=False,
                ai_called=False,
            )

        degraded: list[str] = []
        try:
            ranked = tuple(self._reranker.rerank(query.strip(), candidates))
            if not ranked:
                raise RerankerError("EMPTY_RERANK", "reranker returned no candidates")
        except (RerankerError, TimeoutError, OSError):
            ranked = candidates
            degraded.append("RERANKER")

        try:
            self._answer_service.answer(project_id.strip(), query.strip(), ranked)
        except AIError as exc:
            return RagExecutionResult(
                status="AI_UNAVAILABLE",
                user_message_code="RAG_AI_RETRY" if exc.retryable else "RAG_AI_FAILED",
                retryable=exc.retryable,
                ai_called=True,
                degraded_components=tuple(degraded),
                citation_ids=tuple(item.candidate_id for item in ranked),
                error_code=exc.code,
            )
        return RagExecutionResult(
            status="COMPLETED",
            user_message_code="RAG_OK",
            retryable=False,
            ai_called=True,
            degraded_components=tuple(degraded),
            citation_ids=tuple(item.candidate_id for item in ranked),
        )
