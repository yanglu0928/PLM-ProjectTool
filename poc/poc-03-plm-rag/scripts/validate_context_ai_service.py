from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
POC04_SRC = POC_DIR.parent / "poc-04-ai-gateway" / "src"
sys.path.insert(0, str(POC04_SRC))
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.context_builder import (  # noqa: E402
    AIInvocationPolicy,
    ContextBuilder,
    ContextChunk,
    PromptDefinition,
    RagAIOrchestrator,
)
from poc04_gateway import AIResponse, AIService, ModelRouter, RetryPolicy  # noqa: E402


class RecordingProvider:
    provider_id = "poc-recording-provider"

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return AIResponse(
            text='{"answer":"变更审批应保留影响分析和审批记录。","citations":["C1","C2"]}',
            model=request.model,
            provider=self.provider_id,
            finish_reason="stop",
            usage={"total_tokens": 24},
        )

    def stream(self, request) -> Iterator[str]:
        del request
        yield "unused"

    def close(self) -> None:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Context Builder to AIService routing.")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    provider = RecordingProvider()
    router = ModelRouter()
    router.register(provider)
    service = AIService(router, retry_policy=RetryPolicy(max_attempts=1))
    orchestrator = RagAIOrchestrator(service, ContextBuilder(max_characters=1_200))
    prompt = PromptDefinition(
        prompt_id="RAG_ANSWER",
        task_type="OUTPUT_SUMMARIZE",
        version="v1",
        system_prompt="Use only retrieved context and return JSON with citations.",
        user_template="Question:\n{query}\n\nEvidence:\n{context}",
        output_schema={
            "type": "object",
            "required": ["answer", "citations"],
            "properties": {
                "answer": {"type": "string"},
                "citations": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
    )
    response, package = orchestrator.complete(
        project_id="PROJECT-POC03",
        query="工程变更审批需要保留哪些追溯信息？",
        chunks=(
            ContextChunk("CH-001", "change.docx#p3", "应完成影响分析并保留审批记录。", 0.95),
            ContextChunk("CH-002", "change.docx#p4", "批准后应记录版本和生效日期。", 0.86),
            ContextChunk("CH-003", "meeting.docx#p1", "项目周会应准备参会名单。", 0.12),
        ),
        prompt=prompt,
        policy=AIInvocationPolicy("poc-recording-provider", "poc-model"),
    )
    recorded = provider.requests[0]
    status = (
        "PASS"
        if len(provider.requests) == 1
        and response.structured is not None
        and recorded.metadata["prompt_id"] == "RAG_ANSWER"
        and recorded.metadata["prompt_version"] == "v1"
        and recorded.metadata["project_id"] == "PROJECT-POC03"
        and list(package.included_chunk_ids) == recorded.metadata["context_chunk_ids"]
        else "FAIL"
    )
    report = {
        "schema_version": "poc-03.context-ai-service-result.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": status,
        "routing": {
            "entrypoint": "RagAIOrchestrator",
            "gateway": type(service).__name__,
            "router": type(router).__name__,
            "provider_adapter": type(provider).__name__,
            "direct_provider_call_from_rag": False,
            "ai_service_call_count": len(provider.requests),
        },
        "trace": {
            "project_id": recorded.metadata["project_id"],
            "prompt_id": recorded.metadata["prompt_id"],
            "prompt_version": recorded.metadata["prompt_version"],
            "context_chunk_ids": recorded.metadata["context_chunk_ids"],
            "context_truncated": recorded.metadata["context_truncated"],
            "structured_output_validated": response.structured is not None,
        },
        "privacy": {
            "customer_content_used": False,
            "query_text_committed": False,
            "context_text_committed": False,
            "ai_output_text_committed": False,
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
