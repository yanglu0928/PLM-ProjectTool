from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
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

    def answer(self, project_id, query, candidates):
        del project_id, query, candidates
        if self.error:
            raise self.error
        return "synthetic answer"


def run(retrieval, reranker, answer):
    return SafeRagExecutor(retrieval, reranker, answer).execute(
        project_id="PROJECT-POC03", query="fixed synthetic query"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RAG failure and empty-result behavior.")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    reliable = (
        RetrievedItem("C-01", 0.91, "fixed synthetic candidate one"),
        RetrievedItem("C-02", 0.82, "fixed synthetic candidate two"),
    )
    scenarios = {
        "database_unavailable": run(
            RetrievalStub(error=RetrievalUnavailable("simulated")), RerankStub(), AnswerStub()
        ),
        "empty_retrieval": run(RetrievalStub(), RerankStub(), AnswerStub()),
        "below_reliability_threshold": run(
            RetrievalStub((RetrievedItem("C-LOW", 0.49, "synthetic"),)),
            RerankStub(),
            AnswerStub(),
        ),
        "reranker_unavailable": run(
            RetrievalStub(reliable),
            RerankStub(RerankerError("HTTP_429", "simulated")),
            AnswerStub(),
        ),
        "ai_unavailable": run(
            RetrievalStub(reliable),
            RerankStub(),
            AnswerStub(AIError("AI_PROVIDER_UNAVAILABLE", "simulated", retryable=True)),
        ),
        "success": run(RetrievalStub(reliable), RerankStub(), AnswerStub()),
    }
    expected = {
        "database_unavailable": "RETRIEVAL_UNAVAILABLE",
        "empty_retrieval": "NO_RELIABLE_MATCH",
        "below_reliability_threshold": "NO_RELIABLE_MATCH",
        "reranker_unavailable": "COMPLETED",
        "ai_unavailable": "AI_UNAVAILABLE",
        "success": "COMPLETED",
    }
    status = (
        "PASS"
        if all(scenarios[name].status == expected[name] for name in expected)
        and scenarios["reranker_unavailable"].degraded_components == ("RERANKER",)
        and not scenarios["empty_retrieval"].ai_called
        and not scenarios["below_reliability_threshold"].ai_called
        else "FAIL"
    )
    report = {
        "schema_version": "poc-03.resilience-result.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": status,
        "minimum_reliable_score": 0.5,
        "scenarios": {
            name: result.to_sanitized_dict() for name, result in scenarios.items()
        },
        "privacy": {
            "customer_content_used": False,
            "query_text_committed": False,
            "candidate_content_committed": False,
            "ai_output_committed": False,
            "exception_message_committed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
