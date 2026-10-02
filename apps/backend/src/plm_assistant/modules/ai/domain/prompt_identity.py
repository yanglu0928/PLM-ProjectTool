"""Deployment PromptTemplate identity; no PromptVersion or runnable content."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class PromptIdentityError(ValueError):
    pass


class PromptTaskType(StrEnum):
    DOCUMENT_PARSE = "DOCUMENT_PARSE"
    CAPABILITY_EXTRACT = "CAPABILITY_EXTRACT"
    GAP_ANALYSIS = "GAP_ANALYSIS"
    SURVEY_GENERATE = "SURVEY_GENERATE"
    SURVEY_ANALYZE = "SURVEY_ANALYZE"
    REQUIREMENT_NORMALIZE = "REQUIREMENT_NORMALIZE"
    REQUIREMENT_MATCH = "REQUIREMENT_MATCH"
    SOLUTION_SUGGEST = "SOLUTION_SUGGEST"
    PROTOTYPE_GENERATE = "PROTOTYPE_GENERATE"
    SOLUTION_GENERATE = "SOLUTION_GENERATE"
    PLAN_GENERATE = "PLAN_GENERATE"
    OUTPUT_SUMMARIZE = "OUTPUT_SUMMARIZE"


@dataclass(frozen=True, slots=True)
class PromptTemplateIdentity:
    prompt_template_id: uuid.UUID
    task_type: PromptTaskType

    def __post_init__(self) -> None:
        if (type(self.prompt_template_id) is not uuid.UUID or self.prompt_template_id.int == 0
                or type(self.task_type) is not PromptTaskType):
            raise PromptIdentityError("invalid PromptTemplate identity")
