from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview, EgressPreviewError, EgressPreviewPolicy,
    EgressPreviewPolicyRegistry, EgressPreviewQuery, EgressPreviewService,
    EgressPreviewSourceView, EgressPreviewView, EgressRoute,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
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
        tx = _Tx(); self.items.append(tx); return tx


class _Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class _Guard:
    def require_valid(self, **_kwargs): return object()


class _Authorization:
    def __init__(self): self.operations = []
    def require_in_transaction(self, *_args, **kwargs): self.operations.append(kwargs["operation"])


class _Inputs:
    def __init__(self, resolved): self.resolved = resolved; self.calls = 0
    def resolve_all(self, *_args, **_kwargs): self.calls += 1; return self.resolved


class _Repository:
    def __init__(self, route, view):
        self.route, self.view, self.creates, self.gets = route, view, 0, 0
    def resolve_route(self, *_args, **_kwargs): return self.route
    def create(self, *_args, **_kwargs): self.creates += 1; return self.view
    def get(self, *_args, **_kwargs): self.gets += 1; return self.view


class _Receipts:
    def __init__(self, replay=None): self.replay = replay; self.completed = []
    def reserve(self, *_args, **_kwargs): return self.replay
    def complete(self, *_args, **kwargs): self.completed.append(kwargs["result"])


class _Audit:
    def __init__(self): self.events = []
    def append(self, _tx, event): self.events.append(event); return uuid.uuid4()


class EgressPreviewTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 8, tzinfo=timezone.utc)
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.public = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
        self.command = CreateEgressPreview(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, "gap.analysis.v1",
            "AI_TASK", uuid.uuid4(), uuid.uuid4(), (self.public,),
            ("TECHNICAL_DOCUMENT",), "minimum.document.text.v1",
            1, 65536, 4096, 3, b"p" * 32,
        )
        self.resolved = (AIResolvedInputVersionRef(
            "DOC-02", "document", "DOCUMENT_VERSION", self.public.resource_id,
            self.public.version_id, "PROJECT", self.project,
        ),)
        self.route = EgressRoute(
            self.command.provider_id, uuid.uuid4(), self.command.model_id, "cn-beijing",
        )
        self.view = EgressPreviewView(
            uuid.uuid4(), self.project, self.command.purpose_ref, "AI_TASK",
            self.route.provider_id, self.route.provider_config_version_id,
            self.route.model_id, self.route.data_region,
            self.command.allowed_data_categories,
            (EgressPreviewSourceView("DOC-02", self.public.resource_id, self.public.version_id),),
            self.command.minimal_payload_policy_ref, 1, 65536, 4096, 3,
            b"p" * 32, b"s" * 32, ("EXTERNAL_PROVIDER",),
            self.now, self.now + timedelta(minutes=30),
        )

    def service(self, *, replay=None, policy_bytes=65536):
        self.uow, self.authorization = _Uow(), _Authorization()
        self.inputs = _Inputs(self.resolved)
        self.repo = _Repository(self.route, self.view)
        self.receipts, self.audit = _Receipts(replay), _Audit()
        policy = EgressPreviewPolicy(
            "minimum.document.text.v1", frozenset({"AI_TASK"}),
            frozenset({"TECHNICAL_DOCUMENT"}), timedelta(minutes=30),
            10, policy_bytes, 8192, 3, ("EXTERNAL_PROVIDER",),
        )
        return EgressPreviewService(
            unit_of_work=self.uow, access=_Access(self.actor), license_guard=_Guard(),
            authorization=self.authorization, input_resolver=self.inputs,
            policies=EgressPreviewPolicyRegistry({policy.reference: policy}),
            repository=self.repo, receipts=self.receipts, audit=self.audit,
            clock=lambda: self.now,
        )

    def test_create_commits_preview_audit_and_receipt(self):
        result = self.service().create(self.command, idempotency_key="P" * 16)
        self.assertEqual(result, self.view)
        self.assertEqual((self.inputs.calls, self.repo.creates), (1, 1))
        self.assertEqual(self.receipts.completed, [
            IdempotencyResult("V1_EGRESS_PREVIEW_CREATE", self.view.preview_id, 201),
        ])
        self.assertEqual(len(self.audit.events), 1)
        self.assertTrue(self.uow.items[0].committed)
        self.assertEqual(len(result.preview_fingerprint), 32)

    def test_replay_does_not_resolve_sources_or_route_again(self):
        replay = IdempotencyResult("V1_EGRESS_PREVIEW_CREATE", self.view.preview_id, 201)
        result = self.service(replay=replay).create(self.command, idempotency_key="R" * 16)
        self.assertEqual(result, self.view)
        self.assertEqual((self.inputs.calls, self.repo.creates, self.repo.gets), (0, 0, 1))
        self.assertEqual(len(self.audit.events), 0)

    def test_policy_cannot_be_exceeded(self):
        service = self.service(policy_bytes=1024)
        with self.assertRaises(EgressPreviewError) as raised:
            service.create(self.command, idempotency_key="D" * 16)
        self.assertEqual(raised.exception.code, "AI_EGRESS_POLICY_DENIED")
        self.assertEqual(self.repo.creates, 0)

    def test_get_reauthorizes_before_and_after_license(self):
        result = self.service().get(
            EgressPreviewQuery(b"s" * 32, uuid.uuid4(), self.project),
            preview_id=self.view.preview_id,
        )
        self.assertEqual(result, self.view)
        self.assertEqual(self.authorization.operations, ["EGRESS_PREVIEW_GET"] * 2)
        self.assertEqual(self.repo.gets, 1)

    def test_invalid_collection_rejected_before_dependencies(self):
        invalid = CreateEgressPreview(
            self.command.session_token, self.command.csrf_token, self.command.trace_id,
            self.command.project_id, self.command.purpose_ref, self.command.operation_type,
            self.command.provider_id, self.command.model_id, self.command.source_refs,
            ("TECHNICAL_DOCUMENT", "TECHNICAL_DOCUMENT"),
            self.command.minimal_payload_policy_ref, self.command.estimated_record_count,
            self.command.max_payload_bytes, self.command.max_input_tokens,
            self.command.max_retry_attempts, self.command.payload_fingerprint,
        )
        with self.assertRaises(EgressPreviewError) as raised:
            self.service().create(invalid, idempotency_key="I" * 16)
        self.assertEqual(raised.exception.code, "VALIDATION_FAILED")
        self.assertEqual(len(self.uow.items), 0)


if __name__ == "__main__":
    unittest.main()
