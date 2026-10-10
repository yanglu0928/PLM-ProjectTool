from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.rag.application.reconcile_expired_build import (
    ExpiredRAGEmbeddingBuildReconciler,
    RAGEmbeddingBuildReconciliationError,
    ReconciledRAGEmbeddingBuildFailure,
)


class _Transaction:
    def __init__(self) -> None: self.committed = False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def commit(self): self.committed = True


class _Store:
    def __init__(self, value=None, *, fail=False): self.value, self.fail = value, fail
    def reconcile_next(self, transaction):
        del transaction
        if self.fail: raise RuntimeError("private database detail")
        return self.value


class _Audit:
    def __init__(self, *, fail=False): self.fail, self.draft = fail, None
    def append(self, transaction, draft):
        del transaction
        if self.fail: raise RuntimeError("audit unavailable")
        self.draft = draft
        return uuid.uuid4()


class _Actor:
    def __init__(self, actor=None): self.actor = actor or uuid.uuid4()
    def assert_current(self): return self.actor


class RAGExpiredBuildReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = ReconciledRAGEmbeddingBuildFailure(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "PROJECT", uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), 0, "RAG_BUILD_LEASE_EXPIRED", False,
            datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
        )

    def test_reconciliation_and_audit_commit_together(self) -> None:
        transaction, audit = _Transaction(), _Audit()
        result = ExpiredRAGEmbeddingBuildReconciler(
            unit_of_work=lambda: transaction, store=_Store(self.result),
            audit=audit, system_actor=_Actor(),
        ).reconcile_next()
        self.assertIs(result, self.result)
        self.assertTrue(transaction.committed)
        self.assertEqual(audit.draft.action, "RAG_INDEX_BUILD_RECONCILED")
        self.assertEqual(audit.draft.target_version_id, self.result.embedding_build_id)

    def test_running_batch_requires_unknown_non_retryable_outcome(self) -> None:
        unknown = replace(
            self.result, prior_running_batch_count=1,
            error_code="RAG_PROVIDER_OUTCOME_UNKNOWN",
        )
        unknown.__post_init__()
        for changes in (
            {"retryable": True},
            {"prior_running_batch_count": 1},
            {"scope": "GLOBAL"},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                    RAGEmbeddingBuildReconciliationError):
                replace(self.result, **changes)

    def test_store_audit_or_actor_failure_is_closed(self) -> None:
        cases = (
            (_Store(fail=True), _Audit(), _Actor()),
            (_Store(self.result), _Audit(fail=True), _Actor()),
            (_Store(self.result), _Audit(), _Actor(uuid.UUID(int=0))),
        )
        for store, audit, actor in cases:
            with self.subTest(store=store, audit=audit), self.assertRaises(
                    RAGEmbeddingBuildReconciliationError):
                ExpiredRAGEmbeddingBuildReconciler(
                    unit_of_work=lambda: _Transaction(), store=store,
                    audit=audit, system_actor=actor,
                ).reconcile_next()


if __name__ == "__main__":
    unittest.main()
