from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaim
from plm_assistant.modules.rag.application.fts_retrieval_merge import (
    FTSRetrievalMergePlanner,
)
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    PreparedRAGRetrieval,
    RAGRetrievalPreparationError,
)
from plm_assistant.modules.rag.application.project_fts_candidates import (
    ProjectFTSCandidate,
    ProjectFTSCandidatePlan,
)
from plm_assistant.modules.rag.application.retrieval_terminal import (
    PublishedRAGRetrievalTerminal,
    RAGRetrievalTerminalError,
)
from plm_assistant.modules.rag.application.retrieval_cancel import (
    ReconciledRAGRetrievalCancel,
)
from plm_assistant.modules.rag.application.retrieval_worker import (
    RAGRetrievalOneShotWorker,
)


class _Claims:
    def __init__(self, claim): self.claim = claim
    def claim_next(self, **_kwargs): return self.claim


class _Preparation:
    def __init__(self, prepared, error=None):
        self.prepared, self.error = prepared, error
    def consume_current_query(self, *, consumer, **_kwargs):
        if self.error:
            raise self.error
        return consumer(object(), self.prepared)


class _Candidates:
    def __init__(self, plan=None, error=None): self.value, self.error = plan, error
    def plan(self, _transaction, *, prepared):
        if self.error:
            raise self.error
        return self.value


class _Terminal:
    def __init__(self, success, failure=None, success_error=None,
                 failure_error=None):
        self.success, self.failure = success, failure
        self.success_error, self.failure_error = success_error, failure_error
        self.failed_with = None
    def publish_success_in_transaction(self, *_args, **_kwargs):
        if self.success_error:
            raise self.success_error
        return self.success
    def publish_failure(self, **kwargs):
        self.failed_with = kwargs["error_code"]
        if self.failure_error:
            raise self.failure_error
        return self.failure


class _Cancellations:
    def __init__(self, result=None): self.result, self.calls = result, 0
    def reconcile_current_if_requested(self, **_kwargs):
        self.calls += 1
        return self.result


class RAGRetrievalWorkerTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.job, self.run, self.project, self.actor, self.trace = (
            uuid.uuid4() for _ in range(5))
        self.index, self.model = uuid.uuid4(), uuid.uuid4()
        self.claim = RAGRetrievalClaim(
            self.job, self.run, self.project, self.actor, self.trace,
            1, 1, now, now + timedelta(minutes=5),
        )
        self.prepared = PreparedRAGRetrieval(
            self.run, self.job, self.project, self.actor, self.trace,
            self.index, self.model, {}, "fts.project.v1", 5,
            b"a" * 32, b"q" * 32, bytearray(b"query"),
        )
        candidate = ProjectFTSCandidate(
            0, self.index, self.model, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), "PROJECT_RECORD", {"locator_type": "NODE"},
            "FTS", 100, b"a" * 32,
        )
        self.candidates = ProjectFTSCandidatePlan(
            self.run, self.project, self.index, b"q" * 32, (candidate,),
        )
        self.bundle = uuid.uuid4()
        self.success = PublishedRAGRetrievalTerminal(
            self.run, self.job, self.project, self.actor, self.trace,
            "SUCCEEDED", 1, self.bundle, b"b" * 32, None, now,
        )
        self.failure = PublishedRAGRetrievalTerminal(
            self.run, self.job, self.project, self.actor, self.trace,
            "FAILED", 0, None, None, "RAG_NO_AUTHORIZED_CANDIDATES", now,
        )

    def worker(self, *, claim_present=True, preparation_error=None,
               candidate_error=None, terminal=None, cancellations=None):
        return RAGRetrievalOneShotWorker(
            claims=_Claims(self.claim if claim_present else None),
            preparation=_Preparation(self.prepared, preparation_error),
            candidates=_Candidates(self.candidates, candidate_error),
            merge=FTSRetrievalMergePlanner(),
            terminal=terminal or _Terminal(self.success, self.failure),
            cancellations=cancellations,
        )

    def test_cooperative_cancel_finishes_before_query_decryption(self):
        cancellation = _Cancellations(ReconciledRAGRetrievalCancel(
            self.run, self.job, self.project, self.actor, self.trace,
            "RELEASED", datetime.now(timezone.utc),
        ))
        preparation = _Preparation(self.prepared)
        worker = RAGRetrievalOneShotWorker(
            claims=_Claims(self.claim), preparation=preparation,
            candidates=_Candidates(self.candidates),
            merge=FTSRetrievalMergePlanner(),
            terminal=_Terminal(self.success, self.failure),
            cancellations=cancellation,
        )
        preparation.consume_current_query = lambda **_kwargs: self.fail(
            "cancelled Retrieval must not decrypt query content"
        )
        result = worker.run_once(worker_ref="rag-worker-1")
        self.assertEqual(result.state, "CANCELLED")
        self.assertEqual(cancellation.calls, 1)


    def test_success_returns_context_identity(self):
        result = self.worker().run_once(worker_ref="rag-worker-1")
        self.assertEqual(result.state, "SUCCEEDED")
        self.assertEqual(result.context_bundle_id, self.bundle)
        self.assertEqual(result.candidate_count, 1)

    def test_idle_has_no_identity(self):
        result = self.worker(claim_present=False).run_once(worker_ref="rag-worker-1")
        self.assertEqual(result.state, "IDLE")
        self.assertIsNone(result.job_id)

    def test_zero_candidates_publish_known_failure(self):
        terminal = _Terminal(self.success, self.failure)
        error = RAGRetrievalPreparationError("RAG_NO_AUTHORIZED_CANDIDATES")
        result = self.worker(candidate_error=error, terminal=terminal).run_once(
            worker_ref="rag-worker-1")
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(terminal.failed_with, "RAG_NO_AUTHORIZED_CANDIDATES")

    def test_other_preparation_errors_are_minimized(self):
        terminal = _Terminal(self.success, PublishedRAGRetrievalTerminal(
            self.run, self.job, self.project, self.actor, self.trace,
            "FAILED", 0, None, None,
            "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE",
            datetime.now(timezone.utc),
        ))
        result = self.worker(
            preparation_error=RAGRetrievalPreparationError("RESOURCE_NOT_FOUND"),
            terminal=terminal,
        ).run_once(worker_ref="rag-worker-1")
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(
            terminal.failed_with, "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE")

    def test_uncertain_terminal_does_not_replay(self):
        terminal = _Terminal(
            self.success, self.failure,
            success_error=RAGRetrievalTerminalError(
                "RAG_RETRIEVAL_TERMINAL_UNAVAILABLE"),
        )
        result = self.worker(terminal=terminal).run_once(
            worker_ref="rag-worker-1")
        self.assertEqual(result.state, "RECONCILIATION_PENDING")


if __name__ == "__main__":
    unittest.main()
