from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.create_task import AuthorizedEgressSnapshot
from plm_assistant.modules.ai.application.request_task_retry import (
    AITaskJobRetryOwner,
    AITaskRetryBinding,
    AITaskRetryEgressProof,
    AITaskRetryGeneration,
)
from plm_assistant.modules.ai.application.task_job_read_projection import AITaskJobReadProjection
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts
from plm_assistant.modules.jobs.application.retry_request import JobRetryError, RequestJobRetry
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from unit.test_ai_suggestion_success import _Audit, _Uow


class _Guard:
    def require_valid(self, **_kwargs):
        return object()


class _Access:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor


class _Projects:
    def __init__(self, actor, project, role="IMPLEMENTATION_MEMBER"):
        self.proof = AuthorizedProjectAction(actor, project, "JOB_PROJECT_RETRY", role)

    def require_in_transaction(self, *_args, **_kwargs):
        return self.proof


class _Receipts:
    def __init__(self, replay=None):
        self.replay, self.completed = replay, []

    def reserve(self, *_args, **_kwargs):
        return self.replay

    def complete(self, _tx, *, scope, result):
        self.completed.append((scope, result))


class _Egress:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def resolve_authorized(self, *_args, **_kwargs):
        self.calls += 1
        return self.snapshot


class _Repo:
    def __init__(self, binding, generation):
        self.binding_value, self.generation = binding, generation
        self.created = 0

    def binding(self, *_args, **_kwargs):
        return self.binding_value

    def create(self, *_args, **_kwargs):
        self.created += 1
        return self.generation

    def record_lineage(self, _tx, *, draft, retry_audit_event_id):
        return AITaskRetryGeneration(
            draft.source_ai_task_id, draft.source_job_id,
            draft.new_ai_task_id, draft.new_job_id, draft.project_id,
            draft.requested_by, draft.root_ai_task_id, draft.generation_no,
            draft.expected_source_version, retry_audit_event_id,
            self.generation.created_at,
        )

    def replay(self, *_args, **_kwargs):
        return self.generation


class _ReadRepo:
    def __init__(self, retryable):
        self.value = retryable

    def retryable(self, *_args, **_kwargs):
        return self.value


class AITaskRetryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)
        self.actor, self.creator, self.project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.task, self.job = uuid.uuid4(), uuid.uuid4()
        self.authorization, self.provider, self.config = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.model, self.approver, self.plan = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.snapshot = AuthorizedEgressSnapshot(
            self.authorization, self.project, "project-gap-analysis.v1",
            self.provider, self.config, self.model, "cn-beijing",
            ("DOCUMENT_TEXT",), b"a" * 32, b"b" * 32, b"c" * 32,
            self.approver, "PROJECT_MANAGER", self.now - timedelta(days=1),
            self.now + timedelta(days=1), "minimal.v1", 100, 10000, 1000,
            3, "AUTHORIZED", self.plan,
        )
        proof = AITaskRetryEgressProof(
            self.authorization, "project-gap-analysis.v1", self.provider,
            self.config, self.model, "cn-beijing", ("DOCUMENT_TEXT",),
            b"a" * 32, b"b" * 32, b"c" * 32, self.approver,
            "PROJECT_MANAGER", self.now - timedelta(days=1),
            self.now + timedelta(days=1), self.plan, 10000, 1000, 3,
            "AUTHORIZED",
        )
        self.binding = AITaskRetryBinding(
            self.task, self.job, self.project, self.creator, "GAP_ANALYSIS",
            "FAILED", True, b"d" * 32, 5, 7, proof,
        )
        self.generation = AITaskRetryGeneration(
            self.task, self.job, uuid.uuid4(), uuid.uuid4(), self.project,
            self.actor, self.task, 1, 7, uuid.uuid4(), self.now,
        )
        self.command = RequestJobRetry(
            self.job, self.project, b"s" * 32, b"c" * 32,
            uuid.uuid4(), 7,
        )

    def service(self, *, role="PROJECT_MANAGER", replay=None, snapshot=None):
        repo = _Repo(self.binding, self.generation)
        receipts = _Receipts(replay)
        audit = _Audit()
        owner = AITaskJobRetryOwner(
            unit_of_work=_Uow(), repository=repo,
            session_access=_Access(self.actor),
            projects=_Projects(self.actor, self.project, role),
            license_guard=_Guard(), egress_owner=_Egress(snapshot or self.snapshot),
            receipts=receipts, audit=audit, clock=lambda: self.now,
        )
        return owner, repo, receipts, audit

    def test_manager_can_create_a_fresh_generation_with_audit(self):
        owner, repo, receipts, audit = self.service()
        result = owner.retry(self.command, idempotency_key="1234567890abcdef")
        self.assertEqual(result.source_job_id, self.job)
        self.assertEqual(result.job_id, self.generation.new_job_id)
        self.assertEqual(repo.created, 1)
        self.assertEqual(receipts.completed[0][1].ref_id,
                         self.generation.new_ai_task_id)
        event = audit.events[0][1]
        self.assertEqual(event.action, "AI_TASK_USER_RETRY_REQUESTED")
        self.assertEqual(event.target_version_id, self.task)

    def test_same_receipt_replays_without_creating_generation(self):
        receipt = IdempotencyResult(
            "V1_AI_TASK_USER_RETRY", self.generation.new_ai_task_id, 202,
        )
        owner, repo, receipts, audit = self.service(replay=receipt)
        result = owner.retry(self.command, idempotency_key="1234567890abcdef")
        self.assertEqual(result.job_id, self.generation.new_job_id)
        self.assertEqual(repo.created, 0)
        self.assertFalse(receipts.completed)
        self.assertFalse(audit.events)

    def test_non_creator_non_manager_is_hidden(self):
        owner, _, _, _ = self.service(role="IMPLEMENTATION_MEMBER")
        with self.assertRaises(JobRetryError) as caught:
            owner.retry(self.command, idempotency_key="1234567890abcdef")
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_stale_etag_is_rejected(self):
        owner, _, _, _ = self.service()
        command = RequestJobRetry(
            self.job, self.project, b"s" * 32, b"c" * 32,
            uuid.uuid4(), 6,
        )
        with self.assertRaises(JobRetryError) as caught:
            owner.retry(command, idempotency_key="1234567890abcdef")
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")

    def test_changed_live_egress_is_not_retryable(self):
        changed = AuthorizedEgressSnapshot(
            self.snapshot.authorization_ref, self.snapshot.project_id,
            self.snapshot.purpose_ref, self.snapshot.ai_provider_id,
            self.snapshot.provider_config_version_id, self.snapshot.ai_model_id,
            self.snapshot.data_region, self.snapshot.allowed_data_categories,
            b"z" * 32, self.snapshot.preview_payload_fingerprint,
            self.snapshot.source_refs_fingerprint, self.snapshot.approved_by,
            self.snapshot.approved_role, self.snapshot.approved_at,
            self.snapshot.valid_until, self.snapshot.minimal_payload_policy_ref,
            self.snapshot.max_record_count, self.snapshot.max_payload_bytes,
            self.snapshot.max_input_tokens, self.snapshot.max_retry_attempts,
            self.snapshot.authorization_state, self.snapshot.content_plan_ref,
        )
        owner, _, _, _ = self.service(snapshot=changed)
        with self.assertRaises(JobRetryError) as caught:
            owner.retry(self.command, idempotency_key="1234567890abcdef")
        self.assertEqual(caught.exception.code, "JOB_NOT_RETRYABLE")

    def test_job_projection_exposes_only_retry_boolean(self):
        facts = JobReadFacts(
            self.job, "ai", "AI_TASK_EXECUTE", "PROJECT", self.project,
            self.creator, "FAILED", 1, self.now - timedelta(hours=1), self.now, 7,
        )
        value = AITaskJobReadProjection(repository=_ReadRepo(True)).project(
            object(), facts=facts, actor_id=self.actor,
            project_role="PROJECT_MANAGER",
        )
        self.assertTrue(value.retryable)
        self.assertIsNone(value.result_id)


if __name__ == "__main__":
    unittest.main()
