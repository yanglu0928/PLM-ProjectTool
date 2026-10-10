from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentPlanError,
    AIExecutionContentProjection,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionEnvelopeError,
    AIExecutionTokenEstimate,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
    require_envelope_for_grant,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptTaskContent,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionInputRef,
)


class _WrongEstimator:
    estimator_ref = "wrong-result.v1"
    estimator_version = 1

    def estimate(self, **kwargs):
        return AIExecutionTokenEstimate(
            "different.v1", 1, kwargs["provider_model_key"],
            kwargs["model_revision"], 1,
        )


class AIExecutionEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = uuid.uuid4()
        self.content_plan = uuid.uuid4()
        self.input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            uuid.uuid4(), uuid.uuid4(), self.project_id,
        )
        self.system = "System policy.{context}"
        self.user = "Input={input}\nParameters={parameters}"
        system_hash = hashlib.sha256(self.system.encode()).hexdigest()
        user_hash = hashlib.sha256(self.user.encode()).hexdigest()
        self.grant = AITaskExecutionGrant(
            uuid.uuid4(), self.project_id, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), 1, 7, "GAP_ANALYSIS", (self.input_ref,), b"s" * 32,
            "gap-analysis.v1", 1, uuid.uuid4(), 1, system_hash, user_hash,
            "deepseek-chat.v1", "gap-output.v1", 1, "no-retrieval.v1",
            b"t" * 32, uuid.uuid4(), uuid.uuid4(), b"a" * 32,
            "gap.analysis.v1", uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            "deepseek-chat", "PROVIDER_MANAGED", "cn-beijing",
            ("DOCUMENT_TEXT",), b"x" * 32, "minimum.document.text.v1",
            10, 1_000_000, 1_000_000, 3,
            datetime.now(timezone.utc) + timedelta(minutes=20),
            self.content_plan,
        )
        projection_payload = json.dumps({
            "nodes": [{"kind": "TEXT_LINE", "node_id": "line-1",
                       "text": "需求正文"}],
            "schema_version": "document-minimum-text-v1",
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        self.source = AIExecutionContentSourceIdentity(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            self.input_ref.object_id, self.input_ref.version_id, self.project_id,
            "DOCUMENT_PARSED_TEXT", uuid.uuid4(), uuid.uuid4(),
            "PLAIN_TEXT", "1", "document.parse-result.v1",
            "document.parse.fixed.v1", b"d" * 32, b"e" * 32,
            hashlib.sha256(projection_payload).digest(), 500, 1,
        )
        self.projection = AIExecutionContentProjection(
            self.source, "document.minimum-text.v1", 1, projection_payload,
        )
        self.prompt = AIExecutionPromptIdentity(
            "gap-analysis.v1", 1, self.grant.prompt_template_id, 1,
            system_hash, user_hash, "deepseek-chat.v1", "gap-output.v1", 1,
            "strict-placeholders.v1", 1,
        )
        self.plan = AIExecutionContentPlan(
            self.content_plan, 1, self.project_id, "gap.analysis.v1",
            "GAP_ANALYSIS", b"s" * 32, (self.source,), self.prompt,
            b"t" * 32, AIExecutionContextIdentity(
                "no-retrieval.v1", "NONE"),
            self.grant.ai_provider_id, self.grant.provider_config_version_id,
            self.grant.ai_model_id, "deepseek-chat", "PROVIDER_MANAGED",
            "cn-beijing", ("DOCUMENT_TEXT",), "minimum.document.text.v1",
            "provider-neutral-json.v1", 1,
            "utf8-byte-upper-bound.v1", 1,
        )
        self.prompt_content = AIExecutionPromptTaskContent(
            self.grant.ai_task_id, self.project_id, self.grant.job_id,
            self.grant.requested_by, self.grant.trace_id, "GAP_ANALYSIS",
            "gap-analysis.v1", 1, self.grant.prompt_template_id, 1,
            self.system, self.user, system_hash, user_hash,
            "deepseek-chat.v1", "gap-output.v1", 1, "no-retrieval.v1",
            {"language": "zh-CN"}, b"t" * 32,
        )
        self.builder = AIExecutionEnvelopeBuilder(
            renderer=StrictAIExecutionPromptRenderer(),
            context_policies=AIExecutionContextPolicyRegistry(
                frozenset({"no-retrieval.v1"})),
            token_estimators=AIExecutionTokenEstimatorRegistry((
                Utf8ByteUpperBoundTokenEstimator(),)),
        )

    def test_build_is_canonical_deterministic_and_authorized(self):
        first = self.builder.build(
            plan=self.plan, sources=(self.projection,),
            prompt_content=self.prompt_content,
        )
        second = self.builder.build(
            plan=self.plan, sources=(self.projection,),
            prompt_content=self.prompt_content,
        )
        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.payload_fingerprint, second.payload_fingerprint)
        payload = json.loads(first.canonical_bytes)
        self.assertEqual(payload["schema_version"], "provider-neutral-chat.v1")
        self.assertEqual(payload["model"]["key"], "deepseek-chat")
        self.assertIn("需求正文", payload["messages"][1]["content"])
        self.assertNotIn("source_locator", payload["messages"][1]["content"])
        approved = replace(
            self.grant, approved_payload_fingerprint=first.payload_fingerprint)
        proof = require_envelope_for_grant(
            approved, self.plan, first, now=datetime.now(timezone.utc))
        self.assertEqual(proof.payload_fingerprint, first.payload_fingerprint)
        self.assertEqual(proof.record_count, 1)
        self.assertNotIn("需求正文", repr(first))

    def test_projection_fingerprint_and_source_order_are_enforced(self):
        with self.assertRaises(AIExecutionContentPlanError):
            AIExecutionContentProjection(
                self.source, "document.minimum-text.v1", 1, b'{"other":true}')
        wrong_source = replace(
            self.source, content_revision_id=uuid.uuid4())
        wrong_projection = replace(
            self.projection, source=wrong_source)
        with self.assertRaisesRegex(
                AIExecutionEnvelopeError,
                "AI_EXECUTION_SOURCE_PROJECTION_MISMATCH"):
            self.builder.build(
                plan=self.plan, sources=(wrong_projection,),
                prompt_content=self.prompt_content,
            )

    def test_rag_requires_registered_policy_and_owner_text(self):
        rag_plan = replace(
            self.plan, context=AIExecutionContextIdentity(
                "project-documents.v1", "RAG_CONTEXT", uuid.uuid4(),
                uuid.uuid4(), b"g" * 32, 1, 20))
        rag_content = replace(
            self.prompt_content, context_policy_ref="project-documents.v1")
        unknown = replace(
            self.plan, context=AIExecutionContextIdentity("other-none.v1", "NONE"))
        unknown_content = replace(
            self.prompt_content, context_policy_ref="other-none.v1")
        for plan, content in ((rag_plan, rag_content), (unknown, unknown_content)):
            with self.subTest(policy=plan.context.context_policy_ref), self.assertRaisesRegex(
                    AIExecutionEnvelopeError,
                    "AI_EXECUTION_CONTEXT_POLICY_UNSUPPORTED"):
                self.builder.build(
                    plan=plan, sources=(self.projection,), prompt_content=content)
        rag_builder = AIExecutionEnvelopeBuilder(
            renderer=StrictAIExecutionPromptRenderer(),
            context_policies=AIExecutionContextPolicyRegistry(
                frozenset({"no-retrieval.v1"}),
                frozenset({"project-documents.v1"}),
            ),
            token_estimators=AIExecutionTokenEstimatorRegistry((
                Utf8ByteUpperBoundTokenEstimator(),)),
        )
        with self.assertRaisesRegex(
                AIExecutionEnvelopeError,
                "AI_EXECUTION_CONTEXT_POLICY_UNSUPPORTED"):
            rag_builder.build(
                plan=rag_plan, sources=(self.projection,),
                prompt_content=rag_content,
            )
        envelope = rag_builder.build(
            plan=rag_plan, sources=(self.projection,),
            prompt_content=rag_content,
            context_text='{"schema_version":"rag-context-minimum-text.v1"}',
        )
        self.assertEqual(
            envelope.context_bundle_fingerprint,
            rag_plan.context.context_bundle_fingerprint,
        )
        self.assertIn("rag-context-minimum-text.v1", envelope.canonical_bytes.decode())

    def test_unknown_or_inconsistent_estimator_fails_closed(self):
        unknown = replace(
            self.plan, token_estimator_ref="unknown-estimator.v1")
        with self.assertRaisesRegex(
                AIExecutionEnvelopeError,
                "AI_EXECUTION_TOKEN_ESTIMATOR_UNSUPPORTED"):
            self.builder.build(
                plan=unknown, sources=(self.projection,),
                prompt_content=self.prompt_content)
        builder = AIExecutionEnvelopeBuilder(
            renderer=StrictAIExecutionPromptRenderer(),
            context_policies=AIExecutionContextPolicyRegistry(
                frozenset({"no-retrieval.v1"})),
            token_estimators=AIExecutionTokenEstimatorRegistry((
                _WrongEstimator(),)),
        )
        wrong_plan = replace(
            self.plan, token_estimator_ref="wrong-result.v1")
        with self.assertRaisesRegex(
                AIExecutionEnvelopeError,
                "AI_EXECUTION_TOKEN_ESTIMATE_INVALID"):
            builder.build(
                plan=wrong_plan, sources=(self.projection,),
                prompt_content=self.prompt_content)

    def test_payload_hash_limits_expiry_and_plan_drift_are_rejected(self):
        envelope = self.builder.build(
            plan=self.plan, sources=(self.projection,),
            prompt_content=self.prompt_content)
        approved = replace(
            self.grant, approved_payload_fingerprint=envelope.payload_fingerprint)
        cases = (
            replace(approved, approved_payload_fingerprint=b"z" * 32),
            replace(approved, max_payload_bytes=envelope.payload_bytes - 1),
            replace(approved, max_input_tokens=envelope.input_tokens - 1),
            replace(approved, valid_until=datetime.now(timezone.utc)
                    - timedelta(seconds=1)),
        )
        for grant in cases:
            with self.subTest(grant=grant), self.assertRaises(
                    AIExecutionEnvelopeError):
                require_envelope_for_grant(
                    grant, self.plan, envelope, now=datetime.now(timezone.utc))
        drifted = replace(
            self.plan, model_revision="DIFFERENT_REVISION")
        with self.assertRaises(AIExecutionEnvelopeError):
            require_envelope_for_grant(
                approved, drifted, envelope, now=datetime.now(timezone.utc))

    def test_byte_upper_bound_is_versioned_and_rejects_empty_messages(self):
        estimator = Utf8ByteUpperBoundTokenEstimator()
        value = estimator.estimate(
            provider_model_key="deepseek-chat",
            model_revision="PROVIDER_MANAGED",
            system_utf8=b"system", user_utf8="正文".encode())
        self.assertEqual(value.input_tokens, 6 + len("正文".encode()) + 16)
        with self.assertRaises(AIExecutionEnvelopeError):
            estimator.estimate(
                provider_model_key="deepseek-chat",
                model_revision="PROVIDER_MANAGED",
                system_utf8=b"", user_utf8=b"user")


if __name__ == "__main__":
    unittest.main()
