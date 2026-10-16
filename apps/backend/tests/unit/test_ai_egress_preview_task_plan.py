from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview,
    EgressPreviewError,
    EgressPreviewPolicy,
    EgressPreviewPolicyRegistry,
    EgressPreviewService,
    EgressPreviewSourceView,
    EgressPreviewView,
    EgressRoute,
)
from plm_assistant.modules.ai.application.egress_task_plan import (
    AIExecutionPreviewPlanBuilder,
    AITaskPreviewPlanRequest,
)
from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentProjection,
    AIExecutionContentSourceIdentity,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
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
    AIInputResourceVersionRef,
    AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField,
    AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class _Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def commit(self): self.committed = True


class _Uow:
    def __init__(self): self.items = []
    def __call__(self):
        item = _Tx(); self.items.append(item); return item


class _Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class _Guard:
    def require_valid(self, **_kwargs): return object()


class _Authorization:
    def require_in_transaction(self, *_args, **_kwargs): return object()


class _Inputs:
    def __init__(self, value): self.value, self.calls = value, 0
    def resolve_all(self, *_args, **_kwargs): self.calls += 1; return self.value


class _PromptOwner:
    def __init__(self, content): self.content, self.calls = content, 0
    def resolve_current(self, *_args, **_kwargs):
        self.calls += 1
        return self.content


class _SourceOwner:
    selection_policy_ref = "document.parse.fixed.v1"

    def __init__(self): self.calls = 0

    def resolve_projection(self, _transaction, query, input_ref):
        self.calls += 1
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
            b"s" * 32, b"c" * 32, hashlib.sha256(content).digest(), 512, 1,
        )
        return AIExecutionContentProjection(
            source, "document.minimum-text.v1", 1, content,
        )


class _PlanRepository:
    def __init__(self): self.value = None
    def get_by_id(self, _tx, *, content_plan_id):
        return self.value if self.value and self.value.plan.content_plan_id == content_plan_id else None
    def get_by_preview(self, _tx, *, egress_preview_id):
        return self.value if self.value and self.value.egress_preview_id == egress_preview_id else None
    def add(self, _tx, *, value): self.value = value


class _PreviewRepository:
    def __init__(self, route, now):
        self.route, self.now, self.view, self.request = route, now, None, None

    def resolve_route(self, *_args, **_kwargs): return self.route

    def create(self, _tx, *, request):
        self.request = request
        self.view = EgressPreviewView(
            uuid.uuid4(), request.project_id, request.purpose_ref,
            request.operation_type, request.route.provider_id,
            request.route.provider_config_version_id, request.route.model_id,
            request.route.data_region, request.allowed_data_categories,
            tuple(EgressPreviewSourceView(
                value.resource_type, value.object_id, value.version_id,
            ) for value in request.sources),
            request.minimal_payload_policy_ref, request.estimated_record_count,
            request.max_payload_bytes, request.max_input_tokens,
            request.max_retry_attempts, request.payload_fingerprint,
            request.source_refs_fingerprint, request.risk_codes,
            self.now, request.expires_at,
        )
        return self.view

    def get(self, *_args, **_kwargs): return self.view


class _Receipts:
    def __init__(self): self.replay, self.completed = None, []
    def reserve(self, *_args, **_kwargs): return self.replay
    def complete(self, *_args, **kwargs): self.completed.append(kwargs["result"])


class _Audit:
    def append(self, *_args, **_kwargs): return uuid.uuid4()


class EgressPreviewTaskPlanTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 9, tzinfo=timezone.utc)
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.public = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
        self.resolved = (AIResolvedInputVersionRef(
            "DOC-02", "document", "DOCUMENT_VERSION", self.public.resource_id,
            self.public.version_id, "PROJECT", self.project,
        ),)
        prompt_id = uuid.uuid4()
        system, user = "System {parameters}", "Input {input}"
        prompt = AIExecutionPromptPlanningContent(
            "GAP_ANALYSIS", "gap-analysis.v1", 1, prompt_id, 1,
            system, user, hashlib.sha256(system.encode()).hexdigest(),
            hashlib.sha256(user.encode()).hexdigest(), "deepseek-chat.v1",
            "gap-output.v1", 1, "no-retrieval.v1", {"language": "zh-CN"},
            hashlib.sha256(b'{"language":"zh-CN"}').digest(),
        )
        policy = AITaskSubmissionPolicy(
            "gap-analysis.v1", 1, "GAP_ANALYSIS", prompt_id,
            "project-gap-analysis.v1", "gap-output.v1", "no-retrieval.v1",
            (AITaskParameterField("language", "STRING", True, 16),),
        )
        self.prompt_owner, self.source_owner = _PromptOwner(prompt), _SourceOwner()
        builder = AIExecutionPreviewPlanBuilder(
            task_policies=AITaskSubmissionPolicyRegistry({policy.reference: policy}),
            prompt_owner=self.prompt_owner,
            source_owners={"DOC-02": self.source_owner},
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
        self.plan_repository = _PlanRepository()
        self.plan_owner = AIExecutionContentPlanOwner(self.plan_repository)
        self.route = EgressRoute(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "cn-beijing",
            "deepseek-chat", "PROVIDER_MANAGED",
        )
        self.preview_repository = _PreviewRepository(self.route, self.now)
        self.inputs, self.receipts, self.uow = (
            _Inputs(self.resolved), _Receipts(), _Uow(),
        )
        egress_policy = EgressPreviewPolicy(
            "minimum.document.text.v1", frozenset({"AI_TASK"}),
            frozenset({"DOCUMENT_TEXT"}), timedelta(minutes=30),
            10, 65536, 8192, 3, ("EXTERNAL_PROVIDER",),
        )
        self.service = EgressPreviewService(
            unit_of_work=self.uow, access=_Access(self.actor),
            license_guard=_Guard(), authorization=_Authorization(),
            input_resolver=self.inputs,
            policies=EgressPreviewPolicyRegistry({egress_policy.reference: egress_policy}),
            repository=self.preview_repository, receipts=self.receipts,
            audit=_Audit(), task_plan_builder=builder,
            content_plan_owner=self.plan_owner, clock=lambda: self.now,
        )
        self.command = CreateEgressPreview(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            "project-gap-analysis.v1", "AI_TASK", self.route.provider_id,
            self.route.model_id, (self.public,), ("DOCUMENT_TEXT",),
            "minimum.document.text.v1", None, 65536, 8192, 3, None,
            AITaskPreviewPlanRequest(
                "GAP_ANALYSIS", "gap-analysis.v1", "gap-output.v1",
                "no-retrieval.v1", {"language": "zh-CN"},
            ),
        )

    def test_server_plan_preview_and_receipt_are_one_result(self):
        view = self.service.create(self.command, idempotency_key="A" * 16)
        persisted = self.plan_repository.value
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.egress_preview_id, view.preview_id)
        self.assertEqual(persisted.payload_fingerprint, view.payload_fingerprint)
        self.assertEqual(persisted.record_count, view.estimated_record_count)
        self.assertEqual(self.preview_repository.request.payload_fingerprint,
                         view.payload_fingerprint)
        self.assertTrue(self.uow.items[0].committed)
        self.assertEqual(self.receipts.completed, [
            IdempotencyResult("V1_EGRESS_PREVIEW_CREATE", view.preview_id, 201),
        ])

        self.receipts.replay = self.receipts.completed[0]
        replay = self.service.create(self.command, idempotency_key="A" * 16)
        self.assertEqual(replay, view)
        self.assertEqual((self.inputs.calls, self.prompt_owner.calls,
                          self.source_owner.calls), (1, 1, 1))

    def test_replay_without_persisted_plan_fails_closed(self):
        view = self.service.create(self.command, idempotency_key="B" * 16)
        self.receipts.replay = IdempotencyResult(
            "V1_EGRESS_PREVIEW_CREATE", view.preview_id, 201,
        )
        self.plan_repository.value = None
        with self.assertRaisesRegex(
                EgressPreviewError, "AI_EGRESS_PREVIEW_UNAVAILABLE"):
            self.service.create(self.command, idempotency_key="B" * 16)


if __name__ == "__main__":
    unittest.main()
