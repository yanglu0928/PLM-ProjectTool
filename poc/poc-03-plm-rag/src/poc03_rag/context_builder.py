from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from poc04_gateway import AIRequest, AIResponse, ChatMessage


class ContextBuildError(ValueError):
    """Raised when a context package cannot be built safely."""


class AIServicePort(Protocol):
    def complete(self, request: AIRequest) -> AIResponse: ...


@dataclass(frozen=True, slots=True)
class ContextChunk:
    chunk_id: str
    source_location: str
    content: str
    relevance_score: float

    def __post_init__(self) -> None:
        if not self.chunk_id.strip() or not self.source_location.strip() or not self.content.strip():
            raise ContextBuildError("chunk_id, source_location, and content are required")


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    prompt_id: str
    task_type: str
    version: str
    system_prompt: str
    user_template: str
    output_schema: dict[str, Any]

    def __post_init__(self) -> None:
        values = (
            self.prompt_id,
            self.task_type,
            self.version,
            self.system_prompt,
            self.user_template,
        )
        if any(not value.strip() for value in values):
            raise ContextBuildError("prompt definition fields are required")
        if "{query}" not in self.user_template or "{context}" not in self.user_template:
            raise ContextBuildError("user_template must contain {query} and {context}")


@dataclass(frozen=True, slots=True)
class AIInvocationPolicy:
    provider: str
    model: str
    max_tokens: int = 512
    temperature: float = 0.0

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip():
            raise ContextBuildError("provider and model policy are required")


@dataclass(frozen=True, slots=True)
class ContextPackage:
    rendered_context: str
    included_chunk_ids: tuple[str, ...]
    truncated: bool
    character_count: int


class ContextBuilder:
    def __init__(self, *, max_characters: int = 12_000) -> None:
        if max_characters < 1:
            raise ValueError("max_characters must be positive")
        self._max_characters = max_characters

    def build(self, chunks: Sequence[ContextChunk]) -> ContextPackage:
        if not chunks:
            raise ContextBuildError("at least one context chunk is required")
        ordered = sorted(chunks, key=lambda item: (-item.relevance_score, item.chunk_id))
        sections: list[str] = []
        included_ids: list[str] = []
        used = 0
        truncated = False
        for rank, chunk in enumerate(ordered, start=1):
            section = (
                f"[C{rank}] chunk_id={chunk.chunk_id}; source={chunk.source_location}\n"
                "<retrieved_context>\n"
                f"{chunk.content.strip()}\n"
                "</retrieved_context>"
            )
            separator = "\n\n" if sections else ""
            required = len(separator) + len(section)
            if used + required > self._max_characters:
                truncated = True
                continue
            sections.append(separator + section)
            included_ids.append(chunk.chunk_id)
            used += required
        if not sections:
            raise ContextBuildError("context budget is too small for every chunk")
        return ContextPackage(
            rendered_context="".join(sections),
            included_chunk_ids=tuple(included_ids),
            truncated=truncated,
            character_count=used,
        )


class RagAIOrchestrator:
    def __init__(self, ai_service: AIServicePort, context_builder: ContextBuilder) -> None:
        self._ai_service = ai_service
        self._context_builder = context_builder

    def complete(
        self,
        *,
        project_id: str,
        query: str,
        chunks: Sequence[ContextChunk],
        prompt: PromptDefinition,
        policy: AIInvocationPolicy,
    ) -> tuple[AIResponse, ContextPackage]:
        if not project_id.strip() or not query.strip():
            raise ContextBuildError("project_id and query are required")
        package = self._context_builder.build(chunks)
        user_content = prompt.user_template.format(
            query=query.strip(),
            context=package.rendered_context,
        )
        request = AIRequest(
            task_type=prompt.task_type,
            provider=policy.provider,
            model=policy.model,
            messages=(
                ChatMessage("system", prompt.system_prompt),
                ChatMessage("user", user_content),
            ),
            output_schema=prompt.output_schema,
            max_tokens=policy.max_tokens,
            temperature=policy.temperature,
            metadata={
                "project_id": project_id.strip(),
                "prompt_id": prompt.prompt_id,
                "prompt_version": prompt.version,
                "context_chunk_ids": list(package.included_chunk_ids),
                "context_truncated": package.truncated,
            },
        )
        return self._ai_service.complete(request), package
