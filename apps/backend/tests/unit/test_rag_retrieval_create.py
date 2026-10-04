from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.rag.application.create_retrieval import (
    CreateProjectRetrieval,
    CreatedProjectRetrieval,
    RAGRetrievalCreateError,
    RAGRetrievalCreateService,
    RAGRetrievalCreateTarget,
)
from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    EncryptedRetrievalQuery,
)


class _Tx:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def commit(self): self.committed = True


class _UOW:
    def __init__(self): self.items = []
    def __call__(self):
        tx = _Tx(); self.items.append(tx); return tx


class _Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class _Guard:
    def __init__(self, allowed=True): self.allowed, self.calls = allowed, 0
    def require_valid(self, **_kwargs):
        self.calls += 1
        if not self.allowed: raise RuntimeLicenseError("EXPIRED")


class _Authorization:
    def __init__(self): self.calls = []
    def require_in_transaction(self, *_args, **kwargs): self.calls.append(kwargs)


class _Cipher:
    def __init__(self): self.buffer = None
    def encrypt(self, *, retrieval_run_id, project_id, query_fingerprint,
                plaintext, retention_until):
        self.buffer = plaintext
        return EncryptedRetrievalQuery(
            retrieval_run_id, project_id, query_fingerprint, b"c" * 32,
            {"format": "test", "nonce": "test"}, "test-key.v1",
            len(plaintext), retention_until)


class _Repo:
    def __init__(self, target):
        self.target, self.requests, self.stored = target, [], None
    def locked_target(self, *_args, **_kwargs): return self.target
    def create(self, _tx, *, request):
        self.requests.append(request)
        self.stored = CreatedProjectRetrieval(
            request.retrieval_run_id, uuid.uuid4(), request.project_id,
            request.query_fingerprint)
        return self.stored
    def replay(self, *_args, **_kwargs): return self.stored


class _Receipts:
    def __init__(self, replay=None): self.replay, self.completed = replay, []
    def reserve(self, *_args, **_kwargs): return self.replay
    def complete(self, *_args, **kwargs): self.completed.append(kwargs["result"])


class _Audit:
    def __init__(self): self.events = []
    def append(self, _tx, event): self.events.append(event); return uuid.uuid4()


class RAGRetrievalCreateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)
        self.actor, self.project, self.index, self.model = (
            uuid.uuid4() for _ in range(4))
        self.target = RAGRetrievalCreateTarget(
            self.project, self.index, self.model, None, None)
        self.command = CreateProjectRetrieval(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            "  中文　PLM\n查询  ",
            {"source_type": ["PROJECT_RECORD", "CONTRACTUAL"]},
            self.index, None, "fts.project.v1", "none.v1", 5,
            "R" * 16)

    def service(self, *, actor=True, allowed=True, replay=None, target=True):
        self.uow, self.auth = _UOW(), _Authorization()
        self.guard, self.cipher = _Guard(allowed), _Cipher()
        self.repo = _Repo(self.target if target else None)
        self.receipts, self.audit = _Receipts(replay), _Audit()
        return RAGRetrievalCreateService(
            unit_of_work=self.uow,
            access=_Access(self.actor if actor else None),
            license_guard=self.guard, authorization=self.auth,
            cipher=self.cipher, repository=self.repo,
            receipts=self.receipts, audit=self.audit,
            clock=lambda: self.now)

    def test_create_normalizes_query_filter_and_commits_safe_refs(self):
        result = self.service().create(self.command)
        request = self.repo.requests[0]
        self.assertEqual(request.metadata_filter,
                         {"source_type": ["CONTRACTUAL", "PROJECT_RECORD"]})
        self.assertEqual(request.encrypted_query.plaintext_bytes,
                         len("中文 PLM 查询".encode("utf-8")))
        self.assertEqual(self.cipher.buffer, bytearray(len(self.cipher.buffer)))
        self.assertEqual(self.receipts.completed[0].status_code, 202)
        self.assertEqual(self.audit.events[0].action, "RAG_RETRIEVAL_CREATED")
        self.assertEqual(result.retrieval_state, "RUNNING")
        self.assertTrue(self.uow.items[-1].committed)
        self.assertEqual(self.guard.calls, 2)
        self.assertNotIn(self.command.query, repr(self.command))

    def test_replay_rechecks_current_authority_without_new_write(self):
        service = self.service()
        created = service.create(self.command)
        receipt = IdempotencyResult(
            "V1_RAG_RETRIEVAL_CREATE", created.retrieval_run_id, 202)
        service = self.service(replay=receipt)
        self.repo.stored = created
        self.assertEqual(service.create(self.command), created)
        self.assertEqual(self.repo.requests, [])
        self.assertEqual(self.audit.events, [])
        self.assertEqual(len(self.auth.calls), 2)
        self.assertIsNone(self.cipher.buffer)
        self.assertEqual(self.guard.calls, 2)

    def test_auth_license_and_missing_active_index_fail_closed(self):
        for kwargs, code in (
            ({"actor": False}, "AUTH_ACCESS_DENIED"),
            ({"allowed": False}, "LICENSE_OPERATION_DENIED"),
            ({"target": False}, "RAG_ACTIVE_INDEX_NOT_FOUND"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(RAGRetrievalCreateError) as caught:
                    self.service(**kwargs).create(self.command)
                self.assertEqual(caught.exception.code, code)
                self.assertFalse(any(tx.committed for tx in self.uow.items))
                self.assertIsNone(self.cipher.buffer)

    def test_external_or_unknown_policy_and_arbitrary_filters_are_closed(self):
        changes = (
            {"retrieval_policy_ref": "hybrid.project.v1"},
            {"rerank_policy_ref": "external.rerank.v1"},
            {"global_index_ref": uuid.uuid4()},
            {"metadata_filter": {"sql": "select *"}},
            {"metadata_filter": {"business": {"unknown": "x"}}},
            {"query": "   "},
            {"top_k": 101},
        )
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(RAGRetrievalCreateError) as caught:
                    self.service().create(replace(self.command, **change))
                self.assertIn(caught.exception.code, {
                    "VALIDATION_FAILED", "RAG_METADATA_FILTER_NOT_ALLOWED"})
                self.assertEqual(self.uow.items, [])

    def test_encryption_retention_is_fixed_to_180_days(self):
        self.service().create(self.command)
        encrypted = self.repo.requests[0].encrypted_query
        self.assertEqual(encrypted.retention_until,
                         self.now + timedelta(days=180))


if __name__ == "__main__":
    unittest.main()
