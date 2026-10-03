from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptContentError,
    AIExecutionPromptPlanningContent,
    AIExecutionPromptPlanningOwner,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    ResolvedAITaskSubmissionPolicy,
)


class Repository:
    def __init__(self, value): self.value = value
    def load_current(self, *_args, **_kwargs): return self.value


class AIExecutionPromptPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt_id = uuid.uuid4()
        self.policy = ResolvedAITaskSubmissionPolicy(
            "gap-analysis.v1", 2, "GAP_ANALYSIS", self.prompt_id,
            "project-gap-analysis.v1", "gap-output.v1", "no-retrieval.v1",
            '{"language":"zh-CN"}',
        )
        system, user = "System {parameters}", "Input {input}"
        self.content = AIExecutionPromptPlanningContent(
            "GAP_ANALYSIS", "gap-analysis.v1", 2, self.prompt_id, 3,
            system, user, hashlib.sha256(system.encode()).hexdigest(),
            hashlib.sha256(user.encode()).hexdigest(), "deepseek-chat.v1",
            "gap-output.v1", 1, "no-retrieval.v1",
            {"language": "zh-CN"}, b"t" * 32,
        )

    def test_owner_returns_exact_current_projection_without_sensitive_repr(self) -> None:
        result = AIExecutionPromptPlanningOwner(
            Repository(self.content),
        ).resolve_current(object(), policy=self.policy)
        self.assertIs(result, self.content)
        self.assertNotIn("zh-CN", repr(result))
        self.assertNotIn("System", repr(result))

    def test_owner_fails_closed_on_policy_or_repository_drift(self) -> None:
        for value in (
            None,
            replace(self.content, prompt_policy_version=3),
            replace(self.content, prompt_template_id=uuid.uuid4()),
            replace(self.content, output_schema_ref="other.v1"),
            replace(self.content, context_policy_ref="project-rag.v1"),
        ):
            with self.subTest(value=value), self.assertRaises(
                    AIExecutionPromptContentError):
                AIExecutionPromptPlanningOwner(
                    Repository(value),
                ).resolve_current(object(), policy=self.policy)


if __name__ == "__main__":
    unittest.main()
