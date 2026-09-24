from __future__ import annotations

import inspect
import sys
import unittest
from collections.abc import Iterator
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
POC04_SRC = POC_DIR.parent / "poc-04-ai-gateway" / "src"
sys.path.insert(0, str(POC04_SRC))
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.context_builder import (  # noqa: E402
    AIInvocationPolicy,
    ContextBuildError,
    ContextBuilder,
    ContextChunk,
    PromptDefinition,
    RagAIOrchestrator,
)
from poc04_gateway import AIResponse, AIService, ModelRouter, RetryPolicy  # noqa: E402


OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["answer", "citations"],
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


class RecordingProvider:
    provider_id = "recording-provider"

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return AIResponse(
            text='{"answer":"validated","citations":["C1"]}',
            model=request.model,
            provider=self.provider_id,
            finish_reason="stop",
            usage={"total_tokens": 12},
        )

    def stream(self, request) -> Iterator[str]:
        del request
        yield "unused"

    def close(self) -> None:
        return None


def prompt() -> PromptDefinition:
    return PromptDefinition(
        prompt_id="RAG_ANSWER",
        task_type="OUTPUT_SUMMARIZE",
        version="v1",
        system_prompt="Use only retrieved context and return JSON with citations.",
        user_template="Question:\n{query}\n\nEvidence:\n{context}",
        output_schema=OUTPUT_SCHEMA,
    )


class ContextBuilderTests(unittest.TestCase):
    def test_orders_chunks_and_preserves_source_citations(self) -> None:
        package = ContextBuilder().build(
            (
                ContextChunk("C-LOW", "doc-a#p2", "low", 0.2),
                ContextChunk("C-HIGH", "doc-b#p7", "high", 0.9),
            )
        )
        self.assertEqual(("C-HIGH", "C-LOW"), package.included_chunk_ids)
        self.assertIn("[C1] chunk_id=C-HIGH; source=doc-b#p7", package.rendered_context)
        self.assertIn("<retrieved_context>", package.rendered_context)

    def test_budget_truncates_lower_ranked_chunks(self) -> None:
        first = ContextChunk("C-1", "doc#1", "short", 1.0)
        second = ContextChunk("C-2", "doc#2", "x" * 500, 0.5)
        package = ContextBuilder(max_characters=120).build((first, second))
        self.assertEqual(("C-1",), package.included_chunk_ids)
        self.assertTrue(package.truncated)

    def test_orchestrator_calls_real_ai_service_contract(self) -> None:
        provider = RecordingProvider()
        router = ModelRouter()
        router.register(provider)
        service = AIService(router, retry_policy=RetryPolicy(max_attempts=1))
        orchestrator = RagAIOrchestrator(service, ContextBuilder())
        response, package = orchestrator.complete(
            project_id="PROJECT-001",
            query="How is change approval traced?",
            chunks=(ContextChunk("CH-1", "change.docx#p3", "approval trace", 0.9),),
            prompt=prompt(),
            policy=AIInvocationPolicy("recording-provider", "test-model"),
        )
        self.assertEqual({"answer": "validated", "citations": ["C1"]}, response.structured)
        self.assertEqual(("CH-1",), package.included_chunk_ids)
        request = provider.requests[0]
        self.assertEqual("RAG_ANSWER", request.metadata["prompt_id"])
        self.assertEqual("v1", request.metadata["prompt_version"])
        self.assertEqual("PROJECT-001", request.metadata["project_id"])
        self.assertEqual(["CH-1"], request.metadata["context_chunk_ids"])

    def test_context_module_has_no_provider_transport(self) -> None:
        import poc03_rag.context_builder as module

        source = inspect.getsource(module)
        self.assertNotIn("httpx", source)
        self.assertNotIn("urlopen", source)
        self.assertNotIn("DeepSeekAdapter", source)

    def test_empty_context_is_rejected_before_ai_service(self) -> None:
        with self.assertRaisesRegex(ContextBuildError, "at least one"):
            ContextBuilder().build(())

    def test_prompt_requires_query_and_context_placeholders(self) -> None:
        with self.assertRaisesRegex(ContextBuildError, "must contain"):
            PromptDefinition(
                prompt_id="P",
                task_type="OUTPUT_SUMMARIZE",
                version="v1",
                system_prompt="system",
                user_template="missing placeholders",
                output_schema=OUTPUT_SCHEMA,
            )


if __name__ == "__main__":
    unittest.main()
