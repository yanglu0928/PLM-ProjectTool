from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaim
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    RAGRetrievalExecutionTarget,
    RAGRetrievalPreparationError,
    RAGRetrievalQueryPreparationService,
)
from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    RetrievalQueryEnvelope,
)


class _Transaction:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self) -> None:
        self.committed = True


class _Claims:
    def __init__(self, claim) -> None:
        self.claim = claim
        self.calls = 0

    def check_current(self, transaction, **kwargs):
        del transaction
        self.calls += 1
        assert kwargs["job_id"] == self.claim.job_id
        assert kwargs["fencing_token"] == 1
        return self.claim


class _Guard:
    def __init__(self, fail_at: int | None = None) -> None:
        self.calls = 0
        self.fail_at = fail_at

    def require_valid(self, *, trace_id):
        assert type(trace_id) is uuid.UUID
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeLicenseError("LICENSE_EXPIRED")


class _Authorization:
    def __init__(self, roles=("PROJECT_MANAGER", "PROJECT_MANAGER")) -> None:
        self.roles = list(roles)
        self.calls = 0

    def require_in_transaction(self, transaction, *, user_id, project_id,
                               operation, resource_id=None):
        del transaction, resource_id
        role = self.roles[min(self.calls, len(self.roles) - 1)]
        self.calls += 1
        assert operation == "RAG_RETRIEVAL_EXECUTE"
        return AuthorizedProjectAction(user_id, project_id, operation, role)


class _Repository:
    def __init__(self, target, *, enabled=True) -> None:
        self.target = target
        self.enabled = enabled
        self.target_calls = 0

    def actor_enabled(self, transaction, *, actor_id):
        del transaction, actor_id
        return self.enabled

    def locked_target(self, transaction, *, claim, now):
        del transaction, claim, now
        self.target_calls += 1
        return self.target


class _Cipher:
    def __init__(self, plaintext: bytes) -> None:
        self.plaintext = plaintext
        self.calls = 0
        self.last_buffer = None

    def decrypt(self, envelope):
        assert type(envelope) is RetrievalQueryEnvelope
        self.calls += 1
        self.last_buffer = bytearray(self.plaintext)
        return self.last_buffer


class RAGRetrievalQueryPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
        self.query = "PLM 检索 query"
        self.query_fingerprint = canonical_payload_fingerprint({
            "domain": "rag-query-v1", "query": self.query,
        })
        self.metadata_filter = {"source_type": ["PROJECT_RECORD"]}
        metadata_fingerprint = canonical_payload_fingerprint(self.metadata_filter)
        self.claim = RAGRetrievalClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), 1, 1, self.now, self.now + timedelta(minutes=5),
        )
        envelope = RetrievalQueryEnvelope(
            self.claim.retrieval_run_id, self.claim.project_id,
            self.query_fingerprint, b"ciphertext-that-is-long-enough",
            {"format": "RAG-QUERY-AES-256-GCM-V1", "nonce": "AAAAAAAAAAAAAAAA"},
            "rag-query.v1", len(self.query.encode()), self.now + timedelta(days=1),
        )
        self.target = RAGRetrievalExecutionTarget(
            self.claim.retrieval_run_id, self.claim.job_id, self.claim.project_id,
            self.claim.actor_id, self.claim.trace_id, uuid.uuid4(), uuid.uuid4(),
            1, 3, 2, b"s" * 32, self.metadata_filter,
            metadata_fingerprint, "fts.project.v1", "none.v1", 5, envelope,
        )

    def _service(self, *, repository=None, guard=None, authorization=None,
                 cipher=None):
        transactions = []

        def uow():
            tx = _Transaction()
            transactions.append(tx)
            return tx

        actual_cipher = cipher or _Cipher(self.query.encode())
        service = RAGRetrievalQueryPreparationService(
            unit_of_work=uow, claims=_Claims(self.claim),
            license_guard=guard or _Guard(),
            authorization=authorization or _Authorization(),
            repository=repository or _Repository(self.target),
            cipher=actual_cipher, clock=lambda: self.now,
        )
        return service, actual_cipher, transactions

    def test_authorized_consumer_sees_query_then_buffer_is_zeroed(self) -> None:
        service, cipher, transactions = self._service()
        seen = {}

        def consume(_tx, prepared):
            seen["query"] = bytes(prepared.query_utf8)
            seen["buffer"] = prepared.query_utf8
            return prepared.authorization_snapshot_fingerprint

        result = service.consume_current_query(
            job_id=self.claim.job_id, fencing_token=1,
            worker_ref="rag-retrieval-01", consumer=consume,
        )
        self.assertEqual(seen["query"], self.query.encode())
        self.assertEqual(len(result), 32)
        self.assertEqual(bytes(seen["buffer"]), b"\x00" * len(self.query.encode()))
        self.assertIs(seen["buffer"], cipher.last_buffer)
        self.assertTrue(transactions[-1].committed)

    def test_disabled_actor_or_license_never_reads_key(self) -> None:
        for repository, guard, expected in (
            (_Repository(self.target, enabled=False), _Guard(), "RESOURCE_NOT_FOUND"),
            (_Repository(self.target), _Guard(fail_at=1), "LICENSE_OPERATION_DENIED"),
        ):
            cipher = _Cipher(self.query.encode())
            service, _, _ = self._service(
                repository=repository, guard=guard, cipher=cipher,
            )
            with self.subTest(expected=expected), self.assertRaisesRegex(
                    RAGRetrievalPreparationError, expected):
                service.consume_current_query(
                    job_id=self.claim.job_id, fencing_token=1,
                    worker_ref="rag-retrieval-01", consumer=lambda *_: None,
                )
            self.assertEqual(cipher.calls, 0)

    def test_role_drift_or_target_drift_never_reads_key(self) -> None:
        for authorization, target, expected in (
            (_Authorization(("PROJECT_MANAGER", "CUSTOMER_MANAGER")),
             self.target, "RAG_RETRIEVAL_AUTHORIZATION_CHANGED"),
            (_Authorization(), RAGRetrievalExecutionTarget(
                self.target.retrieval_run_id, uuid.uuid4(), self.target.project_id,
                self.target.actor_id, self.target.trace_id,
                self.target.project_index_ref, self.target.project_model_ref,
                self.target.index_version, self.target.index_lock_version,
                self.target.source_chunk_count, self.target.source_snapshot_fingerprint,
                self.target.metadata_filter, self.target.metadata_filter_fingerprint,
                self.target.retrieval_policy_ref, self.target.rerank_policy_ref,
                self.target.top_k, self.target.query,
             ), "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE"),
        ):
            cipher = _Cipher(self.query.encode())
            service, _, _ = self._service(
                authorization=authorization, repository=_Repository(target),
                cipher=cipher,
            )
            with self.subTest(expected=expected), self.assertRaisesRegex(
                    RAGRetrievalPreparationError, expected):
                service.consume_current_query(
                    job_id=self.claim.job_id, fencing_token=1,
                    worker_ref="rag-retrieval-01", consumer=lambda *_: None,
                )
            self.assertEqual(cipher.calls, 0)

    def test_query_fingerprint_mismatch_is_zeroed(self) -> None:
        bad_query = "different query"
        cipher = _Cipher(bad_query.encode())
        service, _, _ = self._service(cipher=cipher)
        with self.assertRaisesRegex(
                RAGRetrievalPreparationError, "RAG_QUERY_DECRYPTION_UNAVAILABLE"):
            service.consume_current_query(
                job_id=self.claim.job_id, fencing_token=1,
                worker_ref="rag-retrieval-01", consumer=lambda *_: None,
            )
        self.assertEqual(bytes(cipher.last_buffer), b"\x00" * len(bad_query.encode()))

    def test_consumer_failure_is_closed_and_zeroed(self) -> None:
        service, cipher, _ = self._service()
        with self.assertRaisesRegex(
                RAGRetrievalPreparationError,
                "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE"):
            service.consume_current_query(
                job_id=self.claim.job_id, fencing_token=1,
                worker_ref="rag-retrieval-01",
                consumer=lambda *_: (_ for _ in ()).throw(RuntimeError("private")),
            )
        self.assertEqual(bytes(cipher.last_buffer), b"\x00" * len(self.query.encode()))


if __name__ == "__main__":
    unittest.main()
