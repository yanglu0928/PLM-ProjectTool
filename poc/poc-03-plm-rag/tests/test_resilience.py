from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
POC04_SRC = POC_DIR.parent / "poc-04-ai-gateway" / "src"
sys.path.insert(0, str(POC04_SRC))
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.reranker import RerankerError  # noqa: E402
from poc03_rag.resilience import (  # noqa: E402
    RetrievalUnavailable,
    RetrievedItem,
    SafeRagExecutor,
)
from poc04_gateway import AIError  # noqa: E402


class RetrievalStub:
    def __init__(self, result=(), error=None) -> None:
        self.result = result
        self.error = error

    def search(self, project_id, query):
        del project_id, query
        if self.error:
            raise self.error
        return self.result


class RerankStub:
    def __init__(self, error=None) -> None:
        self.error = error

    def rerank(self, query, candidates):
        del query
        if self.error:
            raise self.error
        return tuple(reversed(candidates))


class AnswerStub:
    def __init__(self, error=None) -> None:
        self.error = error
        self.call_count = 0

    def answer(self, project_id, query, candidates):
        del project_id, query, candidates
        self.call_count += 1
        if self.error:
            raise self.error
        return "answer"


RELIABLE = (
    RetrievedItem("C-1", 0.9, "private content one"),
    RetrievedItem("C-2", 0.8, "private content two"),
)


class ResilienceTests(unittest.TestCase):
    def test_database_unavailable_stops_before_ai(self) -> None:
        answer = AnswerStub()
        result = SafeRagExecutor(
            RetrievalStub(error=RetrievalUnavailable("database detail")),
            RerankStub(),
            answer,
        ).execute(project_id="P-1", query="query")
        self.assertEqual("RETRIEVAL_UNAVAILABLE", result.status)
        self.assertTrue(result.retryable)
        self.assertEqual(0, answer.call_count)

    def test_empty_result_does_not_call_ai(self) -> None:
        answer = AnswerStub()
        result = SafeRagExecutor(RetrievalStub(), RerankStub(), answer).execute(
            project_id="P-1", query="query"
        )
        self.assertEqual("NO_RELIABLE_MATCH", result.status)
        self.assertFalse(result.ai_called)
        self.assertEqual(0, answer.call_count)

    def test_below_threshold_does_not_call_ai(self) -> None:
        answer = AnswerStub()
        result = SafeRagExecutor(
            RetrievalStub((RetrievedItem("C-LOW", 0.49, "content"),)),
            RerankStub(),
            answer,
        ).execute(project_id="P-1", query="query")
        self.assertEqual("NO_RELIABLE_MATCH", result.status)
        self.assertEqual(0, answer.call_count)

    def test_reranker_failure_falls_back_and_calls_ai(self) -> None:
        answer = AnswerStub()
        result = SafeRagExecutor(
            RetrievalStub(RELIABLE),
            RerankStub(RerankerError("HTTP_429", "private provider detail")),
            answer,
        ).execute(project_id="P-1", query="query")
        self.assertEqual("COMPLETED", result.status)
        self.assertEqual(("RERANKER",), result.degraded_components)
        self.assertEqual(("C-1", "C-2"), result.citation_ids)
        self.assertEqual(1, answer.call_count)

    def test_ai_unavailable_returns_sanitized_retryable_result(self) -> None:
        answer = AnswerStub(
            AIError("AI_PROVIDER_UNAVAILABLE", "private provider detail", retryable=True)
        )
        result = SafeRagExecutor(RetrievalStub(RELIABLE), RerankStub(), answer).execute(
            project_id="P-1", query="query"
        )
        self.assertEqual("AI_UNAVAILABLE", result.status)
        self.assertTrue(result.retryable)
        report = json.dumps(result.to_sanitized_dict())
        self.assertNotIn("private provider detail", report)
        self.assertNotIn("private content", report)

    def test_success_reports_citations_only(self) -> None:
        result = SafeRagExecutor(
            RetrievalStub(RELIABLE), RerankStub(), AnswerStub()
        ).execute(project_id="P-1", query="query")
        self.assertEqual("COMPLETED", result.status)
        self.assertEqual(("C-2", "C-1"), result.citation_ids)


if __name__ == "__main__":
    unittest.main()
