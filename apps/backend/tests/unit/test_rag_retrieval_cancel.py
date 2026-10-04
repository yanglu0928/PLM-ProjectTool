from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.jobs.application.cancel_request import (
    JobCancelError,
    RequestProjectJobCancel,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.rag.application.retrieval_cancel import (
    CancelledRAGRetrieval,
    RAGRetrievalCancelBinding,
    RAGRetrievalCancelError,
    RAGRetrievalCancelOwner,
    RAGRetrievalCancelReconciler,
    ReconciledRAGRetrievalCancel,
    RequestRAGRetrievalCancel,
)


class Transaction:
    def __init__(self): self.committed = False
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def commit(self): self.committed = True


class _Uow:
    def __init__(self): self.transactions = []
    def __call__(self):
        transaction = Transaction()
        self.transactions.append(transaction)
        return transaction


class _Audit:
    def __init__(self): self.events = []
    def append(self, transaction, event):
        self.events.append((transaction, event))
        return uuid.uuid4()


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Authorization:
    def __init__(self, actor, project, role="IMPLEMENTATION_MEMBER"):
        self.proof = AuthorizedProjectAction(
            actor, project, "JOB_PROJECT_CANCEL", role,
        )

    def require_in_transaction(self, *_args, **_kwargs): return self.proof


class Guard:
    def require_valid(self, **_kwargs): return object()


class Receipts:
    def __init__(self): self.replay, self.completed = None, []
    def reserve(self, *_args, **_kwargs): return self.replay
    def complete(self, _transaction, *, scope, result):
        self.completed.append((scope, result))


class Repository:
    def __init__(self, binding, result):
        self.binding, self.result = binding, result
        self.requested = self.receipted = 0

    def binding_for_job(self, *_args, **_kwargs): return self.binding
    def binding_for_run(self, *_args, **_kwargs): return self.binding

    def request_cancel(self, *_args, **_kwargs):
        self.requested += 1
        return self.result

    def receipt(self, *_args, **_kwargs):
        self.receipted += 1
        return self.result


class SystemActor:
    def __init__(self, actor): self.actor = actor
    def assert_current(self): return self.actor


class ReconcileRepository:
    def __init__(self, result): self.result = result
    def reconcile_current(self, *_args, **_kwargs): return self.result
    def reconcile_expired_next(self, *_args, **_kwargs): return self.result


class RAGRetrievalCancelTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, tzinfo=timezone.utc)
        self.run, self.job, self.project, self.actor, self.trace = (
            uuid.uuid4() for _ in range(5)
        )
        self.binding = RAGRetrievalCancelBinding(
            self.run, self.job, self.project, self.actor, self.trace,
            "RUNNING", "PENDING", 0, 0,
        )
        self.result = CancelledRAGRetrieval(
            self.run, self.job, self.project, "CANCELLED", True,
            1, 2, self.now,
        )
        self.repo = Repository(self.binding, self.result)
        self.receipts, self.uow, self.audit = Receipts(), _Uow(), _Audit()
        self.owner = RAGRetrievalCancelOwner(
            unit_of_work=self.uow, access=Access(self.actor),
            authorization=Authorization(self.actor, self.project),
            license_guard=Guard(), repository=self.repo,
            receipts=self.receipts, audit=self.audit, clock=lambda: self.now,
        )
        self.alias = RequestRAGRetrievalCancel(
            self.run, self.project, b"s" * 32, b"c" * 32, self.trace,
            "用户取消本次检索", 0,
        )
        self.key = "1234567890abcdef"

    def test_alias_commits_shared_owner_and_audits(self):
        result = self.owner.cancel_retrieval(
            self.alias, idempotency_key=self.key,
        )
        self.assertEqual(result, self.result)
        self.assertTrue(self.uow.transactions[0].committed)
        self.assertEqual(self.repo.requested, 1)
        event = self.audit.events[0][1]
        self.assertEqual((event.action, event.before_state, event.after_state), (
            "RAG_RETRIEVAL_CANCELLED", "PENDING", "CANCELLED",
        ))
        receipt = self.receipts.completed[0][1]
        self.assertEqual(receipt.ref_type, "V1_RAG_RETRIEVAL_CANCEL")

    def test_generic_job_adapter_uses_same_owner(self):
        command = RequestProjectJobCancel(
            self.job, self.project, b"s" * 32, b"c" * 32,
            self.trace, "用户取消本次检索", 0,
        )
        result = self.owner.cancel(command, idempotency_key=self.key)
        self.assertEqual((result.job_id, result.state, result.lock_version), (
            self.job, "CANCELLED", 2,
        ))
        self.assertEqual(
            self.receipts.completed[0][1].ref_type,
            "V1_RAG_RETRIEVAL_JOB_CANCEL",
        )

    def test_replay_reauthorizes_and_reads_immutable_proof(self):
        self.receipts.replay = IdempotencyResult(
            "V1_RAG_RETRIEVAL_CANCEL", uuid.uuid4(), 200,
        )
        result = self.owner.cancel_retrieval(
            self.alias, idempotency_key=self.key,
        )
        self.assertEqual(result, self.result)
        self.assertEqual((self.repo.requested, self.repo.receipted), (0, 1))
        self.assertFalse(self.uow.transactions[0].committed)

    def test_wrong_version_and_non_creator_non_manager_fail_closed(self):
        wrong = RequestRAGRetrievalCancel(
            self.run, self.project, b"s" * 32, b"c" * 32,
            self.trace, "用户取消本次检索", 1,
        )
        with self.assertRaises(RAGRetrievalCancelError) as caught:
            self.owner.cancel_retrieval(wrong, idempotency_key=self.key)
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")
        other = uuid.uuid4()
        denied = RAGRetrievalCancelOwner(
            unit_of_work=_Uow(), access=Access(other),
            authorization=Authorization(other, self.project),
            license_guard=Guard(), repository=self.repo,
            receipts=Receipts(), audit=_Audit(), clock=lambda: self.now,
        )
        with self.assertRaises(RAGRetrievalCancelError) as caught:
            denied.cancel_retrieval(self.alias, idempotency_key=self.key)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_generic_adapter_maps_private_failure(self):
        self.repo.request_cancel = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RAGRetrievalCancelError("CONFLICT_STATE")
        )
        command = RequestProjectJobCancel(
            self.job, self.project, b"s" * 32, b"c" * 32,
            self.trace, "用户取消本次检索", 0,
        )
        with self.assertRaises(JobCancelError) as caught:
            self.owner.cancel(command, idempotency_key=self.key)
        self.assertEqual(caught.exception.code, "JOB_UNAVAILABLE")

    def test_worker_and_expired_reconciliation_are_system_audited(self):
        reconciled = ReconciledRAGRetrievalCancel(
            self.run, self.job, self.project, self.actor, self.trace,
            "RELEASED", self.now,
        )
        uow, audit = _Uow(), _Audit()
        service = RAGRetrievalCancelReconciler(
            unit_of_work=uow, repository=ReconcileRepository(reconciled),
            audit=audit, system_actor=SystemActor(uuid.uuid4()),
        )
        self.assertEqual(service.reconcile_current(
            job_id=self.job, fencing_token=1, worker_ref="worker-1",
        ), reconciled)
        self.assertTrue(uow.transactions[0].committed)
        self.assertEqual(audit.events[0][1].reason_code, "USER_REQUESTED")

        expired = ReconciledRAGRetrievalCancel(
            self.run, self.job, self.project, self.actor, self.trace,
            "EXPIRED", self.now,
        )
        uow, audit = _Uow(), _Audit()
        service = RAGRetrievalCancelReconciler(
            unit_of_work=uow, repository=ReconcileRepository(expired),
            audit=audit, system_actor=SystemActor(uuid.uuid4()),
        )
        self.assertEqual(service.reconcile_expired_next(), expired)
        self.assertEqual(audit.events[0][1].reason_code, "LEASE_EXPIRED")


if __name__ == "__main__":
    unittest.main()
