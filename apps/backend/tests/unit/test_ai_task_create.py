from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.create_task import (
    AITaskCreateError, AITaskCreateService, AuthorizedEgressSnapshot,
    CreateAITask, CreatedAITask, input_refs_fingerprint,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField, AITaskPromptSnapshot, AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class _Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.committed = True


class _Uow:
    def __init__(self): self.items = []
    def __call__(self):
        tx = _Tx(); self.items.append(tx); return tx


class _Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class _Guard:
    def require_valid(self, **_kwargs): return object()


class _Authorization:
    def __init__(self): self.calls = 0
    def require_in_transaction(self, *_args, **_kwargs): self.calls += 1


class _Inputs:
    def __init__(self, resolved): self.resolved = resolved; self.calls = 0
    def resolve_all(self, *_args, **_kwargs): self.calls += 1; return self.resolved


class _Egress:
    def __init__(self, snapshot): self.snapshot = snapshot; self.calls = 0
    def resolve_authorized(self, *_args, **_kwargs): self.calls += 1; return self.snapshot


class _PromptOwner:
    def __init__(self, snapshot): self.snapshot = snapshot; self.calls = 0
    def resolve_current(self, *_args, **_kwargs): self.calls += 1; return self.snapshot


class _Repository:
    def __init__(self, result): self.result = result; self.creates = 0; self.replays = 0
    def create(self, *_args, **_kwargs): self.creates += 1; return self.result
    def replay(self, *_args, **_kwargs): self.replays += 1; return self.result


class _Receipts:
    def __init__(self, replay=None): self.replay = replay; self.completed = []
    def reserve(self, *_args, **_kwargs): return self.replay
    def complete(self, *_args, **kwargs): self.completed.append(kwargs["result"])


class _Audit:
    def __init__(self): self.events = []
    def append(self, _tx, event): self.events.append(event); return uuid.uuid4()


class AITaskCreateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.prompt_template = uuid.uuid4()
        public = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
        self.command = CreateAITask(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, "GAP_ANALYSIS",
            (public,), "prompt.gap.v1", "schema.gap.v1", "context.gap.v1",
            {"language": "zh-CN", "max_items": 50}, uuid.uuid4(),
        )
        self.policies = AITaskSubmissionPolicyRegistry({"prompt.gap.v1": AITaskSubmissionPolicy(
            "prompt.gap.v1", 1, "GAP_ANALYSIS", self.prompt_template,
            "gap.analysis.v1", "schema.gap.v1", "context.gap.v1",
            (AITaskParameterField("language", "STRING", True, 16,
                                  allowed_values=("zh-CN", "en-US")),
             AITaskParameterField("max_items", "INTEGER", False,
                                  minimum=1, maximum=100)),
        )})
        self.prompt = AITaskPromptSnapshot(
            self.prompt_template, 1, "prompt.gap.v1", 1, "gap.analysis.v1",
            "schema.gap.v1", "context.gap.v1",
            '{"language": "zh-CN", "max_items": 50}', b"q" * 32,
        )
        self.resolved = (AIResolvedInputVersionRef(
            "DOC-02", "document", "DOCUMENT_VERSION", public.resource_id,
            public.version_id, "PROJECT", self.project,
        ),)
        source = input_refs_fingerprint(self.resolved)
        self.snapshot = AuthorizedEgressSnapshot(
            self.command.egress_authorization_ref, self.project, "gap.analysis.v1",
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "cn-beijing",
            ("TECHNICAL_DOCUMENT",), b"a" * 32, b"p" * 32, source,
            uuid.uuid4(), "PROJECT_MANAGER", self.now - timedelta(minutes=1),
            self.now + timedelta(hours=1), "document-minimal.v1", 1,
            65536, 4096, 3, "AUTHORIZED",
        )
        self.created = CreatedAITask(uuid.uuid4(), uuid.uuid4())

    def service(self, *, receipt=None, snapshot=None):
        self.uow, self.authz = _Uow(), _Authorization()
        self.inputs = _Inputs(self.resolved)
        self.egress = _Egress(snapshot or self.snapshot)
        self.prompt_owner = _PromptOwner(self.prompt)
        self.repo, self.receipts, self.audit = (
            _Repository(self.created), _Receipts(receipt), _Audit(),
        )
        return AITaskCreateService(
            unit_of_work=self.uow, access=_Access(self.actor), license_guard=_Guard(),
            authorization=self.authz, input_resolver=self.inputs,
            egress_owner=self.egress, task_policies=self.policies,
            prompt_owner=self.prompt_owner, repository=self.repo,
            receipts=self.receipts, audit=self.audit, clock=lambda: self.now,
        )

    def test_atomic_create_completes_task_receipt(self):
        result = self.service().create(self.command, idempotency_key="A" * 16)
        self.assertEqual(result, self.created)
        self.assertEqual(
            (self.repo.creates, self.prompt_owner.calls, self.inputs.calls, self.egress.calls),
            (1, 1, 1, 1),
        )
        self.assertEqual(self.receipts.completed, [
            IdempotencyResult("V1_AI_TASK_CREATE", self.created.ai_task_id, 202),
        ])
        self.assertEqual(len(self.audit.events), 1)
        self.assertTrue(self.uow.items[0].committed)

    def test_replay_returns_original_task_and_job_without_owner_calls(self):
        receipt = IdempotencyResult("V1_AI_TASK_CREATE", self.created.ai_task_id, 202)
        result = self.service(receipt=receipt).create(self.command, idempotency_key="B" * 16)
        self.assertEqual(result, self.created)
        self.assertEqual((self.repo.replays, self.repo.creates), (1, 0))
        self.assertEqual(
            (self.prompt_owner.calls, self.inputs.calls, self.egress.calls,
             len(self.audit.events)),
            (0, 0, 0, 0),
        )
        self.assertFalse(self.uow.items[0].committed)

    def test_source_set_mismatch_fails_closed(self):
        invalid = AuthorizedEgressSnapshot(
            self.snapshot.authorization_ref, self.snapshot.project_id, self.snapshot.purpose_ref,
            self.snapshot.ai_provider_id, self.snapshot.provider_config_version_id,
            self.snapshot.ai_model_id, self.snapshot.data_region,
            self.snapshot.allowed_data_categories, self.snapshot.authorization_fingerprint,
            self.snapshot.preview_payload_fingerprint, b"x" * 32, self.snapshot.approved_by,
            self.snapshot.approved_role, self.snapshot.approved_at, self.snapshot.valid_until,
            self.snapshot.minimal_payload_policy_ref, self.snapshot.max_record_count,
            self.snapshot.max_payload_bytes, self.snapshot.max_input_tokens,
            self.snapshot.max_retry_attempts, self.snapshot.authorization_state,
        )
        service = self.service(snapshot=invalid)
        with self.assertRaises(AITaskCreateError) as raised:
            service.create(self.command, idempotency_key="C" * 16)
        self.assertEqual(raised.exception.code, "AI_EGRESS_AUTHORIZATION_INVALID")
        self.assertEqual(self.repo.creates, 0)
        self.assertFalse(self.uow.items[0].committed)

    def test_expired_authorization_fails_closed(self):
        expired = AuthorizedEgressSnapshot(
            self.snapshot.authorization_ref, self.snapshot.project_id, self.snapshot.purpose_ref,
            self.snapshot.ai_provider_id, self.snapshot.provider_config_version_id,
            self.snapshot.ai_model_id, self.snapshot.data_region,
            self.snapshot.allowed_data_categories, self.snapshot.authorization_fingerprint,
            self.snapshot.preview_payload_fingerprint, self.snapshot.source_refs_fingerprint,
            self.snapshot.approved_by, self.snapshot.approved_role,
            self.now - timedelta(hours=2), self.now,
            self.snapshot.minimal_payload_policy_ref, self.snapshot.max_record_count,
            self.snapshot.max_payload_bytes,
            self.snapshot.max_input_tokens, self.snapshot.max_retry_attempts, "AUTHORIZED",
        )
        with self.assertRaises(AITaskCreateError) as raised:
            self.service(snapshot=expired).create(self.command, idempotency_key="D" * 16)
        self.assertEqual(raised.exception.code, "AI_EGRESS_AUTHORIZATION_INVALID")

    def test_invalid_task_rejected_before_dependencies(self):
        invalid = CreateAITask(
            self.command.session_token, self.command.csrf_token, self.command.trace_id,
            self.command.project_id, "FREE_FORM", self.command.input_refs,
            self.command.prompt_policy_ref, self.command.output_schema_ref,
            self.command.context_policy_ref, self.command.task_parameters,
            self.command.egress_authorization_ref,
        )
        with self.assertRaises(AITaskCreateError) as raised:
            self.service().create(invalid, idempotency_key="E" * 16)
        self.assertEqual(raised.exception.code, "VALIDATION_FAILED")
        self.assertEqual(len(self.uow.items), 0)


if __name__ == "__main__":
    unittest.main()
