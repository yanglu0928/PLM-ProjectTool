from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.rag.application.embedding_index_quality import (
    RAGEmbeddingIndexQualityError,
    RAGEmbeddingIndexQualityService,
    RAGEmbeddingIndexQualityTarget,
    RecordedRAGEmbeddingIndexQuality,
    RegisterRAGEmbeddingIndexQuality,
)


class _Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        self.committed = True


class _UOW:
    def __init__(self):
        self.items: list[_Tx] = []

    def __call__(self):
        item = _Tx()
        self.items.append(item)
        return item


class _Access:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor


class _Guard:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = 0

    def require_valid(self, **_kwargs):
        self.calls += 1
        if not self.allowed:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class _Receipts:
    def __init__(self, replay=None):
        self.replay = replay
        self.completed = []

    def reserve(self, *_args, **_kwargs):
        return self.replay

    def complete(self, *_args, **kwargs):
        self.completed.append(kwargs["result"])


class _Audit:
    def __init__(self):
        self.events = []

    def append(self, _tx, event):
        self.events.append(event)
        return uuid.uuid4()


class _Repo:
    def __init__(self, target, now):
        self.target = target
        self.now = now
        self.saved = []
        self.replay = None

    def locked_target(self, *_args, **_kwargs):
        return self.target

    def save(self, _tx, *, target, actor_id, command,
             classification_basis_points, exact_citation_basis_points,
             quality_state, error_code):
        result = RecordedRAGEmbeddingIndexQuality(
            uuid.uuid4(), target.embedding_index_id, actor_id,
            command.dataset_ref, command.dataset_fingerprint,
            command.dataset_case_count, command.classification_correct_count,
            command.exact_citation_correct_count,
            classification_basis_points, exact_citation_basis_points,
            command.project_isolation_pass,
            command.out_of_scope_citation_count,
            command.failure_closure_pass,
            quality_state, error_code, self.now,
        )
        self.saved.append(result)
        return result

    def get(self, *_args, **_kwargs):
        return self.replay


class RAGEmbeddingIndexQualityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, 21, tzinfo=timezone.utc)
        self.actor, self.index, self.validation, self.model = (
            uuid.uuid4() for _ in range(4)
        )
        self.target = RAGEmbeddingIndexQualityTarget(
            self.index, self.validation, "GLOBAL", None, "default.search",
            self.model, b"s" * 32,
        )
        self.command = RegisterRAGEmbeddingIndexQuality(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.index, 2,
            "holdout.2026-10-04.r1", b"d" * 32, b"i" * 32, b"a" * 32,
            50, 45, 49, True, 0, True,
            self.now - timedelta(hours=1), "Q" * 16,
        )

    def service(self, *, actor=True, allowed=True, replay=None):
        self.uow = _UOW()
        self.guard = _Guard(allowed)
        self.receipts = _Receipts(replay)
        self.audit = _Audit()
        self.repo = _Repo(self.target, self.now)
        return RAGEmbeddingIndexQualityService(
            unit_of_work=self.uow,
            access=_Access(self.actor if actor else None),
            license_guard=self.guard,
            repository=self.repo,
            receipts=self.receipts,
            audit=self.audit,
            clock=lambda: self.now,
        )

    def test_exact_threshold_pass_is_server_derived_and_committed(self):
        result = self.service().register(self.command)
        self.assertEqual(
            (result.quality_state, result.classification_basis_points,
             result.exact_citation_basis_points, result.error_code),
            ("PASSED", 9000, 9800, None),
        )
        self.assertEqual(self.guard.calls, 2)
        self.assertEqual(self.receipts.completed[0].ref_type,
                         "V1_RAG_INDEX_QUALITY_REGISTER")
        self.assertEqual(self.audit.events[0].after_state, "QUALITY_PASSED")
        self.assertTrue(self.uow.items[-1].committed)
        self.assertNotIn("quality_state", self.command.__dataclass_fields__)

    def test_each_safety_or_score_failure_is_preserved_as_evidence(self):
        changes = (
            {"classification_correct_count": 44},
            {"exact_citation_correct_count": 48},
            {"project_isolation_pass": False},
            {"out_of_scope_citation_count": 1},
            {"failure_closure_pass": False},
        )
        for change in changes:
            with self.subTest(change=change):
                result = self.service().register(replace(
                    self.command, idempotency_key=str(uuid.uuid4()), **change,
                ))
                self.assertEqual(result.quality_state, "FAILED")
                self.assertEqual(
                    result.error_code, "RAG_BUSINESS_QUALITY_THRESHOLD_FAILED",
                )
                self.assertTrue(self.uow.items[-1].committed)

    def test_replay_reads_immutable_result_without_saving_or_auditing(self):
        stored = _Repo(self.target, self.now).save(
            None, target=self.target, actor_id=self.actor, command=self.command,
            classification_basis_points=9000,
            exact_citation_basis_points=9800,
            quality_state="PASSED", error_code=None,
        )
        receipt = IdempotencyResult(
            "V1_RAG_INDEX_QUALITY_REGISTER", stored.quality_result_id, 200,
        )
        service = self.service(replay=receipt)
        self.repo.replay = stored
        self.assertEqual(service.register(self.command), stored)
        self.assertEqual(self.repo.saved, [])
        self.assertEqual(self.audit.events, [])
        self.assertEqual(self.guard.calls, 2)

    def test_auth_and_license_fail_closed_without_commit(self):
        for kwargs, code in (
            ({"actor": False}, "AUTH_ACCESS_DENIED"),
            ({"allowed": False}, "LICENSE_OPERATION_DENIED"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(RAGEmbeddingIndexQualityError) as caught:
                    self.service(**kwargs).register(self.command)
                self.assertEqual(caught.exception.code, code)
                self.assertFalse(any(item.committed for item in self.uow.items))

    def test_invalid_shape_and_future_seal_are_rejected_before_uow(self):
        changes = (
            {"dataset_ref": "../body"},
            {"dataset_fingerprint": b"short"},
            {"dataset_case_count": 49},
            {"dataset_sealed_at": self.now},
            {"out_of_scope_citation_count": 51},
        )
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(RAGEmbeddingIndexQualityError) as caught:
                    self.service().register(replace(self.command, **change))
                self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
                self.assertEqual(self.uow.items, [])

    def test_result_rejects_false_pass(self):
        with self.assertRaises(RAGEmbeddingIndexQualityError):
            replace(
                self.service().register(self.command),
                classification_basis_points=8800,
                classification_correct_count=44,
            )


if __name__ == "__main__":
    unittest.main()
