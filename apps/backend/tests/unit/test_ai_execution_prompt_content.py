from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptContentError,
    AIExecutionPromptTaskContent,
    AIExecutionPromptTaskContentOwner,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
)


class _Repository:
    def __init__(self, content: AIExecutionPromptTaskContent | None) -> None:
        self.content = content

    def load_exact(self, transaction, *, grant):
        return self.content


class AIExecutionPromptContentTests(unittest.TestCase):
    def setUp(self) -> None:
        project_id = uuid.uuid4()
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), project_id,
        )
        system = "Use only this authorized context:\n{context}"
        user = "Parameters: {parameters}\nInput: {input}"
        import hashlib
        system_hash = hashlib.sha256(system.encode("utf-8")).hexdigest()
        user_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()
        self.grant = AITaskExecutionGrant(
            uuid.uuid4(), project_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            1, 1, "GAP_ANALYSIS", (input_ref,), b"s" * 32,
            "gap-analysis.v1", 1, uuid.uuid4(), 2, system_hash, user_hash,
            "deepseek-chat.v1", "gap-output.v1", 1,
            "project-documents.v1", b"t" * 32, uuid.uuid4(), uuid.uuid4(),
            b"a" * 32, "project-gap-analysis.v1", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), "deepseek-chat", "PROVIDER_MANAGED", "cn-beijing",
            ("DOCUMENT_TEXT",), b"p" * 32, "document-minimal.v1",
            10, 65536, 4096, 3,
            datetime(2026, 10, 3, tzinfo=timezone.utc) + timedelta(minutes=20),
        )
        self.content = AIExecutionPromptTaskContent(
            self.grant.ai_task_id, project_id, self.grant.job_id,
            self.grant.requested_by, self.grant.trace_id, "GAP_ANALYSIS",
            "gap-analysis.v1", 1, self.grant.prompt_template_id, 2,
            system, user, system_hash, user_hash, "deepseek-chat.v1",
            "gap-output.v1", 1, "project-documents.v1",
            {"language": "zh-CN", "max_items": 20}, b"t" * 32,
        )
        source = AIExecutionContentSourceIdentity(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            input_ref.object_id, input_ref.version_id, project_id,
            "DOCUMENT_PARSED_TEXT", uuid.uuid4(), uuid.uuid4(),
            "document-parser.standard", "1.0.0", "document.parse-result.v1",
            "document.parse.fixed.v1", b"d" * 32, b"e" * 32, 100, 1,
        )
        prompt = AIExecutionPromptIdentity(
            "gap-analysis.v1", 1, self.grant.prompt_template_id, 2,
            system_hash, user_hash, "deepseek-chat.v1", "gap-output.v1", 1,
            "strict-placeholders.v1", 1,
        )
        context = AIExecutionContextIdentity(
            "project-documents.v1", "RAG_CONTEXT", uuid.uuid4(), uuid.uuid4(),
            b"g" * 32, 1, 50,
        )
        self.plan = AIExecutionContentPlan(
            uuid.uuid4(), 1, project_id, "project-gap-analysis.v1",
            "GAP_ANALYSIS", b"s" * 32, (source,), prompt, b"t" * 32, context,
            self.grant.ai_provider_id, self.grant.provider_config_version_id,
            self.grant.ai_model_id, "deepseek-chat", "PROVIDER_MANAGED",
            "cn-beijing", ("DOCUMENT_TEXT",), "document-minimal.v1",
            "provider-neutral-json.v1", 1, "deepseek-chat.tokens.v1", 1,
        )

    def test_owner_returns_only_exact_content_and_hides_sensitive_values(self) -> None:
        owner = AIExecutionPromptTaskContentOwner(_Repository(self.content))
        self.assertIs(owner.load_exact(object(), grant=self.grant), self.content)
        self.assertNotIn("authorized context", repr(self.content))
        self.assertNotIn("zh-CN", repr(self.content))
        self.assertNotIn("b't", repr(self.content))
        with self.assertRaises(TypeError):
            self.content.task_parameters["language"] = "en"

    def test_owner_rejects_every_grant_bound_metadata_drift(self) -> None:
        for content in (
            replace(self.content, ai_task_id=uuid.uuid4()),
            replace(self.content, prompt_version_no=3),
            replace(self.content, context_policy_ref="different.v1"),
            replace(self.content, task_parameters_fingerprint=b"x" * 32),
        ):
            with self.subTest(content=content), self.assertRaises(
                    AIExecutionPromptContentError):
                AIExecutionPromptTaskContentOwner(
                    _Repository(content),
                ).load_exact(object(), grant=self.grant)

    def test_renderer_is_utf8_deterministic_and_does_not_expand_inserted_braces(self) -> None:
        renderer = StrictAIExecutionPromptRenderer()
        first = renderer.render(
            self.plan, self.content,
            input_text="Cafe\u0301 {context}\r\n正文",
            context_text="证据\r\nA",
        )
        second = renderer.render(
            self.plan, self.content,
            input_text="Café {context}\n正文",
            context_text="证据\nA",
        )
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertIn(b"{context}", first.user_utf8)
        self.assertEqual(first.parameters_utf8,
                         b'{"language":"zh-CN","max_items":20}')
        self.assertNotIn("正文", repr(first))

    def test_renderer_rejects_unknown_missing_duplicate_or_wrong_context(self) -> None:
        import hashlib

        def variant(*, system: str | None = None,
                    user: str | None = None):
            system_value = system if system is not None else self.content.system_template
            user_value = user if user is not None else self.content.user_template
            system_hash = hashlib.sha256(system_value.encode("utf-8")).hexdigest()
            user_hash = hashlib.sha256(user_value.encode("utf-8")).hexdigest()
            content = replace(
                self.content, system_template=system_value,
                user_template=user_value, system_template_hash=system_hash,
                user_template_hash=user_hash,
            )
            plan = replace(self.plan, prompt=replace(
                self.plan.prompt, system_template_hash=system_hash,
                user_template_hash=user_hash,
            ))
            return plan, content

        cases = (
            variant(user="{input} {unknown} {parameters}"),
            variant(user="No input {parameters}"),
            variant(user="{input} {input} {parameters}"),
            variant(user="{input}"),
            variant(system="No context", user="{input} {parameters}"),
        )
        for plan, content in cases:
            with self.subTest(content=content), self.assertRaises(
                    AIExecutionPromptContentError):
                StrictAIExecutionPromptRenderer().render(
                    plan, content, input_text="正文", context_text="证据",
                )
        with self.assertRaises(AIExecutionPromptContentError):
            StrictAIExecutionPromptRenderer().render(
                self.plan, self.content, input_text="正文", context_text=None,
            )

    def test_renderer_rejects_plan_or_content_drift_and_unsupported_policy(self) -> None:
        renderer = StrictAIExecutionPromptRenderer()
        for plan in (
            replace(self.plan, task_parameters_fingerprint=b"x" * 32),
            replace(self.plan, prompt=replace(
                self.plan.prompt, rendering_policy_ref="other.v1",
            )),
        ):
            with self.subTest(plan=plan), self.assertRaises(
                    AIExecutionPromptContentError):
                renderer.render(
                    plan, self.content, input_text="正文", context_text="证据",
                )

    def test_invalid_prompt_hash_or_parameter_shape_is_rejected(self) -> None:
        for kwargs in (
            {"user_template_hash": "f" * 64},
            {"task_parameters": {"nested": []}},
            {"task_parameters": {"language": " en "}},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(
                    AIExecutionPromptContentError):
                replace(self.content, **kwargs)


if __name__ == "__main__":
    unittest.main()
