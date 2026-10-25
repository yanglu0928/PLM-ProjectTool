"""Immutable declaration of one deployment AI model, not a routing clearance."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import StrEnum


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)


class AIModelDefinitionError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid AI model definition")


class AIModelKind(StrEnum):
    CHAT = "CHAT"
    EMBEDDING = "EMBEDDING"
    RERANK = "RERANK"


@dataclass(frozen=True, slots=True)
class AIModelDefinition:
    model_id: uuid.UUID
    provider_id: uuid.UUID
    provider_model_key: str
    kind: AIModelKind
    revision: str
    embedding_dimension: int | None
    structured_output: bool
    context_window_tokens: int | None

    def __post_init__(self) -> None:
        if (
            type(self.model_id) is not uuid.UUID or self.model_id.int == 0
            or type(self.provider_id) is not uuid.UUID or self.provider_id.int == 0
            or type(self.provider_model_key) is not str or _TOKEN.fullmatch(self.provider_model_key) is None
            or type(self.kind) is not AIModelKind
            or type(self.revision) is not str or _TOKEN.fullmatch(self.revision) is None
            or type(self.structured_output) is not bool
            or self.structured_output and self.kind is not AIModelKind.CHAT
            or self.kind is AIModelKind.EMBEDDING and (
                type(self.embedding_dimension) is not int or not 1 <= self.embedding_dimension <= 65536
            )
            or self.kind is not AIModelKind.EMBEDDING and self.embedding_dimension is not None
            or self.context_window_tokens is not None and (
                type(self.context_window_tokens) is not int or not 1 <= self.context_window_tokens <= 1048576
            )
        ):
            raise AIModelDefinitionError()
