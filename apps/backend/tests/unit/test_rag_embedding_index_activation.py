from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.rag.application.embedding_index_activation import (
    ActivateRAGEmbeddingIndex,
    ActivatedRAGEmbeddingIndex,
    RAGEmbeddingIndexActivationError,
    RAGEmbeddingIndexActivationService,
    RAGEmbeddingIndexActivationTarget,
)


class _Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def commit(self): self.committed = True


class _UOW:
    def __init__(self): self.items = []
    def __call__(self):
        item = _Tx(); self.items.append(item); return item


class _Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class _Guard:
    def __init__(self, enabled=True): self.enabled, self.calls = enabled, 0
    def require_valid(self, **_kwargs):
        self.calls += 1
        if not self.enabled: raise RuntimeLicenseError("EXPIRED")
        return object()


class _Receipts:
    def __init__(self, replay=None): self.replay, self.completed = replay, []
    def reserve(self, *_args, **_kwargs): return self.replay
    def complete(self, *_args, **kwargs): self.completed.append(kwargs["result"])


class _Audit:
    def __init__(self, fail=False): self.fail, self.events = fail, []
    def append(self, _tx, event):
        if self.fail: raise RuntimeError("audit unavailable")
        self.events.append(event); return uuid.uuid4()


class _Repo:
    def __init__(self, target, actor, now):
        self.target, self.actor, self.now = target, actor, now
        self.activated, self.replay = 0, None

    def locked_target(self, *_args, **_kwargs): return self.target

    def activate(self, _tx, *, target, actor_id, audit_event_id, trace_id):
        self.activated += 1
        return ActivatedRAGEmbeddingIndex(
            uuid.uuid4(), target.embedding_index_id, target.quality_result_ref,
            actor_id, audit_event_id, trace_id, target.scope, target.project_id,
            target.index_purpose, target.retired_index_ref, 2, 3,
            target.retired_before_lock_version,
            None if target.retired_before_lock_version is None
            else target.retired_before_lock_version + 1,
            self.now,
        )

    def get(self, *_args, **_kwargs): return self.replay


class RAGEmbeddingIndexActivationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)
        self.actor, self.index, self.quality = (uuid.uuid4() for _ in range(3))
        self.target = RAGEmbeddingIndexActivationTarget(
            self.index, self.quality, "PROJECT", uuid.uuid4(),
            "project.knowledge", "READY", 2,
        )
        self.command = ActivateRAGEmbeddingIndex(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.index, 2, "A" * 16,
        )

    def service(self, *, actor=True, enabled=True, replay=None, audit_fail=False):
        self.uow, self.guard = _UOW(), _Guard(enabled)
        self.receipts, self.audit = _Receipts(replay), _Audit(audit_fail)
        self.repo = _Repo(self.target, self.actor, self.now)
        return RAGEmbeddingIndexActivationService(
            unit_of_work=self.uow,
            access=_Access(self.actor if actor else None),
            license_guard=self.guard,
            repository=self.repo,
            receipts=self.receipts,
            audit=self.audit,
            clock=lambda: self.now,
        )

    def test_activation_commits_quality_audit_and_receipt(self):
        result = self.service().activate(self.command)
        self.assertEqual((result.lock_version, result.retired_index_ref), (3, None))
        self.assertEqual(self.audit.events[0].target_version_id, self.quality)
        self.assertEqual(self.receipts.completed[0].ref_type,
                         "V1_RAG_INDEX_ACTIVATE")
        self.assertEqual((self.repo.activated, self.guard.calls), (1, 2))
        self.assertTrue(self.uow.items[-1].committed)

    def test_switch_captures_retired_versions(self):
        old = uuid.uuid4()
        self.target = replace(
            self.target, retired_index_ref=old, retired_before_lock_version=5,
        )
        result = self.service().activate(self.command)
        self.assertEqual(
            (result.retired_index_ref, result.retired_before_lock_version,
             result.retired_after_lock_version),
            (old, 5, 6),
        )

    def test_replay_rechecks_authority_and_license_without_mutation(self):
        stored = self.service().activate(self.command)
        receipt = IdempotencyResult(
            "V1_RAG_INDEX_ACTIVATE", stored.activation_result_id, 200,
        )
        self.target = replace(self.target, index_state="ACTIVE", lock_version=3)
        service = self.service(replay=receipt)
        self.repo.replay = stored
        self.assertEqual(service.activate(self.command), stored)
        self.assertEqual((self.repo.activated, self.audit.events), (0, []))
        with self.assertRaises(RAGEmbeddingIndexActivationError) as denied:
            self.service(actor=False, replay=receipt).activate(self.command)
        self.assertEqual(denied.exception.code, "AUTH_ACCESS_DENIED")

    def test_stale_target_auth_license_and_audit_fail_closed(self):
        cases = (
            ({"actor": False}, "AUTH_ACCESS_DENIED"),
            ({"enabled": False}, "LICENSE_OPERATION_DENIED"),
            ({"audit_fail": True}, "RAG_INDEX_ACTIVATION_UNAVAILABLE"),
        )
        for kwargs, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(RAGEmbeddingIndexActivationError) as raised:
                    self.service(**kwargs).activate(self.command)
                self.assertEqual(raised.exception.code, code)
                self.assertFalse(any(item.committed for item in self.uow.items))
        self.target = replace(self.target, index_state="ACTIVE", lock_version=3)
        with self.assertRaises(RAGEmbeddingIndexActivationError) as stale:
            self.service().activate(self.command)
        self.assertEqual(stale.exception.code, "CONFLICT_VERSION")

    def test_invalid_command_and_invalid_result_are_rejected(self):
        for change in (
            {"session_token": b"short"},
            {"expected_lock_version": 3},
            {"embedding_index_id": uuid.UUID(int=0)},
        ):
            with self.subTest(change=change):
                with self.assertRaises(RAGEmbeddingIndexActivationError) as raised:
                    self.service().activate(replace(self.command, **change))
                self.assertEqual(raised.exception.code, "VALIDATION_FAILED")
        result = self.service().activate(self.command)
        with self.assertRaises(RAGEmbeddingIndexActivationError):
            replace(result, retired_index_ref=uuid.uuid4())


if __name__ == "__main__":
    unittest.main()
