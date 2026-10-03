from __future__ import annotations

import hashlib
import json
import unittest
import uuid

from plm_assistant.modules.ai.application.egress_task_plan import (
    AIEgressTaskPlanError,
    AIExecutionPreviewPlanBuilder,
    AIExecutionPreviewPlanRequest,
    AIExecutionPreviewRoute,
    AITaskPreviewPlanRequest,
)
from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentProjection,
    AIExecutionContentSourceIdentity,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptPlanningContent,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField,
    AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)


class PromptOwner:
    def __init__(self, content): self.content = content
    def resolve_current(self, *_args, **_kwargs): return self.content


class SourceOwner:
    selection_policy_ref = "document.parse.fixed.v1"

    def resolve_projection(self, _transaction, query, input_ref):
        content = json.dumps({
            "nodes": [{"kind": "TEXT_LINE", "node_id": "n1", "text": "需求"}],
            "schema_version": "document-minimum-text-v1",
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        source = AIExecutionContentSourceIdentity(
            input_ref.ordinal, input_ref.resource_type, input_ref.owner_module,
            input_ref.object_type, input_ref.object_id, input_ref.version_id,
            input_ref.project_id, "DOCUMENT_PARSED_TEXT", uuid.uuid4(),
            uuid.uuid4(), "document-parser.standard", "1.0.0",
            "document.parse-result.v1", query.selection_policy_ref,
            b"r" * 32, b"c" * 32, hashlib.sha256(content).digest(),
            2048, 1,
        )
        return AIExecutionContentProjection(
            source, "document.minimum-text.v1", 1, content,
        )


class AIEgressTaskPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.prompt_id = uuid.uuid4()
        system, user = "System {parameters}", "Input {input}"
        self.prompt = AIExecutionPromptPlanningContent(
            "GAP_ANALYSIS", "gap-analysis.v1", 2, self.prompt_id, 3,
            system, user, hashlib.sha256(system.encode()).hexdigest(),
            hashlib.sha256(user.encode()).hexdigest(), "deepseek-chat.v1",
            "gap-output.v1", 4, "no-retrieval.v1", {"language": "zh-CN"},
            hashlib.sha256(b'{"language":"zh-CN"}').digest(),
        )
        policy = AITaskSubmissionPolicy(
            "gap-analysis.v1", 2, "GAP_ANALYSIS", self.prompt_id,
            "project-gap-analysis.v1", "gap-output.v1", "no-retrieval.v1",
            (AITaskParameterField("language", "STRING", True, 16),),
        )
        self.builder = AIExecutionPreviewPlanBuilder(
            task_policies=AITaskSubmissionPolicyRegistry({policy.reference: policy}),
            prompt_owner=PromptOwner(self.prompt),
            source_owners={"DOC-02": SourceOwner()},
            envelope_builder=AIExecutionEnvelopeBuilder(
                renderer=StrictAIExecutionPromptRenderer(),
                context_policies=AIExecutionContextPolicyRegistry(
                    frozenset({"no-retrieval.v1"}),
                ),
                token_estimators=AIExecutionTokenEstimatorRegistry((
                    Utf8ByteUpperBoundTokenEstimator(),
                )),
            ),
        )
        self.input = AIResolvedInputVersionRef(
            "DOC-02", "document", "DOCUMENT_VERSION", uuid.uuid4(),
            uuid.uuid4(), "PROJECT", self.project,
        )
        self.request = AIExecutionPreviewPlanRequest(
            self.project, uuid.uuid4(), uuid.uuid4(),
            "project-gap-analysis.v1", "document-minimal.v1",
            ("DOCUMENT_TEXT",), (self.input,),
            AIExecutionPreviewRoute(
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
                "deepseek-chat", "PROVIDER_MANAGED", "cn-beijing",
            ),
            AITaskPreviewPlanRequest(
                "GAP_ANALYSIS", "gap-analysis.v1", "gap-output.v1",
                "no-retrieval.v1", {"language": "zh-CN"},
            ),
        )

    def test_builds_server_owned_plan_and_envelope_without_network(self) -> None:
        result = self.builder.build(object(), request=self.request)
        self.assertEqual(result.plan.project_id, self.project)
        self.assertEqual(result.plan.sources[0].object_id, self.input.object_id)
        self.assertEqual(result.envelope.record_count, 1)
        self.assertEqual(result.envelope.payload_fingerprint,
                         hashlib.sha256(result.envelope.canonical_bytes).digest())
        self.assertNotIn("需求", repr(result))
        self.assertNotIn("zh-CN", repr(result))

    def test_policy_prompt_source_and_context_drift_fail_closed(self) -> None:
        wrong_task = AITaskPreviewPlanRequest(
            "SURVEY_ANALYZE", "gap-analysis.v1", "gap-output.v1",
            "no-retrieval.v1", {"language": "zh-CN"},
        )
        with self.assertRaises(AIEgressTaskPlanError):
            self.builder.build(object(), request=AIExecutionPreviewPlanRequest(
                self.request.project_id, self.request.requested_by,
                self.request.trace_id, self.request.purpose_ref,
                self.request.minimal_payload_policy_ref,
                self.request.allowed_data_categories, self.request.inputs,
                self.request.route, wrong_task,
            ))
        unknown = AIResolvedInputVersionRef(
            "OTHER", "document", "DOCUMENT_VERSION", uuid.uuid4(),
            uuid.uuid4(), "PROJECT", self.project,
        )
        with self.assertRaises(AIEgressTaskPlanError):
            self.builder.build(object(), request=AIExecutionPreviewPlanRequest(
                self.request.project_id, self.request.requested_by,
                self.request.trace_id, self.request.purpose_ref,
                self.request.minimal_payload_policy_ref,
                self.request.allowed_data_categories, (unknown,),
                self.request.route, self.request.task,
            ))


if __name__ == "__main__":
    unittest.main()
