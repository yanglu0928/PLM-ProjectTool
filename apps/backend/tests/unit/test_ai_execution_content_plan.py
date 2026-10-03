from __future__ import annotations

import unittest
import uuid
from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentPlanError,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
    content_plan_fingerprint,
    require_content_plan_for_grant,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
)


class AIExecutionContentPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = uuid.uuid4()
        self.input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), self.project_id,
        )
        self.grant = AITaskExecutionGrant(
            uuid.uuid4(), self.project_id, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), 1, 8, "GAP_ANALYSIS", (self.input_ref,), b"s" * 32,
            "gap-analysis.v1", 2, uuid.uuid4(), 3, "a" * 64, "b" * 64,
            "deepseek-chat.v1", "gap-output.v1", 4,
            "project-documents.v1", b"t" * 32, uuid.uuid4(), uuid.uuid4(),
            b"a" * 32, "project-gap-analysis.v1", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), "deepseek-chat", "PROVIDER_MANAGED", "cn-beijing",
            ("DOCUMENT_TEXT",), b"p" * 32, "document-minimal.v1",
            10, 65536, 4096, 3,
            datetime(2026, 10, 3, tzinfo=timezone.utc) + timedelta(minutes=20),
        )
        source = AIExecutionContentSourceIdentity(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            self.input_ref.object_id, self.input_ref.version_id, self.project_id,
            "DOCUMENT_PARSED_TEXT", uuid.uuid4(), uuid.uuid4(),
            "document-parser.standard", "1.0.0", "document.parse-result.v1",
            "document.parse.fixed.v1", b"r" * 32, b"c" * 32, b"p" * 32,
            2048, 6,
        )
        prompt = AIExecutionPromptIdentity(
            "gap-analysis.v1", 2, self.grant.prompt_template_id, 3,
            "a" * 64, "b" * 64, "deepseek-chat.v1", "gap-output.v1", 4,
            "strict-placeholders.v1", 1,
        )
        context = AIExecutionContextIdentity(
            "project-documents.v1", "RAG_CONTEXT", uuid.uuid4(), uuid.uuid4(),
            b"g" * 32, 3, 512,
        )
        self.plan = AIExecutionContentPlan(
            uuid.uuid4(), 1, self.project_id, "project-gap-analysis.v1",
            "GAP_ANALYSIS", b"s" * 32, (source,), prompt, b"t" * 32, context,
            self.grant.ai_provider_id, self.grant.provider_config_version_id,
            self.grant.ai_model_id, "deepseek-chat", "PROVIDER_MANAGED",
            "cn-beijing", ("DOCUMENT_TEXT",), "document-minimal.v1",
            "provider-neutral-json.v1", 1, "deepseek-chat.tokens.v1", 1,
        )

    def test_exact_plan_matches_grant_and_has_stable_no_content_fingerprint(self) -> None:
        first = content_plan_fingerprint(self.plan)
        self.assertEqual(first, content_plan_fingerprint(self.plan))
        self.assertIs(require_content_plan_for_grant(self.grant, self.plan), self.plan)
        self.assertEqual(len(first), 32)
        self.assertNotIn("b'c", repr(self.plan))
        self.assertNotIn("b'r", repr(self.plan))
        names = {item.name for item in fields(AIExecutionContentPlan)}
        self.assertFalse({"content", "prompt_text", "parameters", "storage_locator"} & names)

    def test_exact_content_revision_and_order_change_plan_fingerprint(self) -> None:
        changed_revision = replace(
            self.plan.sources[0], content_revision_id=uuid.uuid4(),
        )
        changed = replace(self.plan, sources=(changed_revision,))
        self.assertNotEqual(content_plan_fingerprint(self.plan),
                            content_plan_fingerprint(changed))

        second = replace(
            self.plan.sources[0], ordinal=2, object_id=uuid.uuid4(),
            version_id=uuid.uuid4(), content_revision_id=uuid.uuid4(),
            content_object_id=uuid.uuid4(),
        )
        ordered = replace(
            self.plan,
            sources=(self.plan.sources[0], second),
        )
        self.assertNotEqual(content_plan_fingerprint(self.plan),
                            content_plan_fingerprint(ordered))

    def test_business_input_or_execution_metadata_drift_is_rejected(self) -> None:
        with self.assertRaises(AIExecutionContentPlanError):
            replace(self.plan, project_id=uuid.uuid4())
        drifts = (
            replace(self.plan, source_refs_fingerprint=b"x" * 32),
            replace(self.plan, purpose_ref="different-purpose.v1"),
            replace(self.plan, task_parameters_fingerprint=b"x" * 32),
            replace(self.plan, ai_model_id=uuid.uuid4()),
            replace(self.plan, model_revision="different"),
            replace(self.plan, minimal_payload_policy_ref="different.v1"),
            replace(self.plan, prompt=replace(
                self.plan.prompt, user_template_hash="f" * 64,
            )),
            replace(self.plan, context=replace(
                self.plan.context, context_policy_ref="different.v1",
            )),
        )
        for plan in drifts:
            with self.subTest(plan=plan), self.assertRaises(
                    AIExecutionContentPlanError):
                require_content_plan_for_grant(self.grant, plan)

    def test_source_identity_must_exactly_match_business_input(self) -> None:
        for source in (
            replace(self.plan.sources[0], object_id=uuid.uuid4()),
            replace(self.plan.sources[0], version_id=uuid.uuid4()),
            replace(self.plan.sources[0], content_fingerprint=b"x" * 32),
        ):
            plan = replace(self.plan, sources=(source,))
            if source.content_fingerprint == self.plan.sources[0].content_fingerprint:
                with self.assertRaises(AIExecutionContentPlanError):
                    require_content_plan_for_grant(self.grant, plan)
            else:
                self.assertIs(require_content_plan_for_grant(self.grant, plan), plan)
                self.assertNotEqual(
                    content_plan_fingerprint(self.plan), content_plan_fingerprint(plan),
                )

    def test_context_none_and_rag_shapes_are_strict(self) -> None:
        empty = AIExecutionContextIdentity("no-retrieval.v1", "NONE")
        self.assertEqual(empty.record_count, 0)
        for kwargs in (
            {"context_policy_ref": "no-retrieval.v1", "mode": "NONE",
             "context_bundle_fingerprint": b"x" * 32},
            {"context_policy_ref": "project-documents.v1", "mode": "RAG_CONTEXT"},
            {"context_policy_ref": "project-documents.v1", "mode": "RAG_CONTEXT",
             "retrieval_run_id": uuid.uuid4(), "context_bundle_id": uuid.uuid4(),
             "context_bundle_fingerprint": b"x" * 32, "record_count": 0,
             "content_size_bytes": 1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(
                    AIExecutionContentPlanError):
                AIExecutionContextIdentity(**kwargs)

    def test_plan_rejects_unordered_categories_and_invalid_source_shape(self) -> None:
        with self.assertRaises(AIExecutionContentPlanError):
            replace(self.plan, allowed_data_categories=("Z_TEXT", "A_TEXT"))
        with self.assertRaises(AIExecutionContentPlanError):
            replace(self.plan.sources[0], content_size_bytes=0)


if __name__ == "__main__":
    unittest.main()
