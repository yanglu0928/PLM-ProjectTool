from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.rag.application.retrieval_read import (
    GetRAGRetrieval,
    RAGContextBundleView,
    RAGContextItemView,
    RAGRetrievalCandidateView,
    RAGRetrievalReadError,
    RAGRetrievalReadService,
    RAGRetrievalResultView,
    RAGRetrievalRunView,
    RAGRetrievalScorePartView,
)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def __init__(self): self.calls = 0
    def require_valid(self, **_kwargs): self.calls += 1


class Authorization:
    def __init__(self, actor, project, role):
        self.actor, self.project, self.role = actor, project, role

    def require_in_transaction(self, *_args, **kwargs):
        return AuthorizedProjectAction(
            self.actor, self.project, kwargs["operation"], self.role,
        )


class Repository:
    def __init__(self, run, result, context):
        self.run, self.result, self.context = run, result, context

    def get_run(self, *_args, **_kwargs): return self.run
    def get_result(self, *_args, **_kwargs): return self.result
    def get_context(self, *_args, **_kwargs): return self.context


class RAGRetrievalReadTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, tzinfo=timezone.utc)
        self.actor, self.creator, self.project, self.run_id = (
            uuid.uuid4() for _ in range(4)
        )
        self.score = RAGRetrievalScorePartView(
            "FINAL", 0, 900_000, 900_000, 1_000_000, 900_000,
            "fts.project.v1",
        )
        self.candidate = RAGRetrievalCandidateView(
            uuid.uuid4(), 0, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            "PROJECT_RECORD", {"locator_type": "PAGE", "page": 1},
            "FTS", 900_000, (self.score,), "PLM result",
        )
        self.run = RAGRetrievalRunView(
            self.run_id, self.project, self.creator, None, uuid.uuid4(),
            "fts.project.v1", "none.v1", 5,
            "NOT_APPLICABLE", "NOT_APPLICABLE", "SUCCEEDED", (), False,
            None, uuid.uuid4(), uuid.uuid4(), 1, self.now, self.now,
        )
        self.result = RAGRetrievalResultView(
            self.run_id, self.project, (self.candidate,), (), False, self.now,
        )
        context_item = RAGContextItemView(
            0, self.candidate.chunk_id, self.candidate.document_version_ref,
            dict(self.candidate.source_locator), 0, 10, 10, "PLM result",
        )
        self.context = RAGContextBundleView(
            uuid.uuid4(), self.run_id, self.project, "project-documents.v1",
            b"b" * 32, 100, 10, (context_item,), self.now,
        )
        self.query = GetRAGRetrieval(
            b"s" * 32, uuid.uuid4(), self.project, self.run_id,
        )

    def service(self, *, actor=None, role="IMPLEMENTATION_MEMBER", run=None,
                result=None, context=None):
        actor = actor or self.actor
        guard = Guard()
        service = RAGRetrievalReadService(
            unit_of_work=Tx, access=Access(actor), license_guard=guard,
            authorization=Authorization(actor, self.project, role),
            repository=Repository(
                self.run if run is None else run,
                self.result if result is None else result,
                self.context if context is None else context,
            ),
            clock=lambda: self.now,
        )
        return service, guard

    def test_creator_can_read_run_result_and_minimum_context(self):
        service, guard = self.service(actor=self.creator)
        self.assertEqual(service.get_run(self.query), self.run)
        self.assertEqual(service.get_result(self.query), self.result)
        self.assertEqual(service.get_context(self.query), self.context)
        self.assertEqual(guard.calls, 6)
        self.assertNotIn("query", repr(self.run).lower())
        self.assertNotIn("query_fingerprint", self.run.__dataclass_fields__)
        self.assertNotIn("PLM result", repr(self.candidate))

    def test_oversight_roles_can_read_non_owned_run(self):
        for role in ("PROJECT_MANAGER", "CUSTOMER_MANAGER"):
            with self.subTest(role=role):
                service, _guard = self.service(role=role)
                self.assertEqual(service.get_result(self.query), self.result)

    def test_ordinary_non_creator_and_cross_project_shape_are_hidden(self):
        service, _guard = self.service(role="IMPLEMENTATION_MEMBER")
        with self.assertRaises(RAGRetrievalReadError) as caught:
            service.get_run(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        other = RAGRetrievalRunView(
            self.run.retrieval_run_id, uuid.uuid4(), self.actor,
            None, self.run.project_index_ref,
            self.run.retrieval_policy_ref, self.run.rerank_policy_ref,
            self.run.top_k, self.run.rerank_state, self.run.egress_state,
            self.run.retrieval_state, (), False, None, self.run.job_id,
            self.run.trace_id, 1, self.now, self.now,
        )
        service, _guard = self.service(role="PROJECT_MANAGER", run=other)
        with self.assertRaises(RAGRetrievalReadError) as caught:
            service.get_run(self.query)
        self.assertEqual(caught.exception.code, "RAG_RETRIEVAL_READ_UNAVAILABLE")

    def test_terminal_payload_is_not_available_before_success(self):
        running = RAGRetrievalRunView(
            self.run.retrieval_run_id, self.run.project_id, self.actor,
            None, self.run.project_index_ref,
            self.run.retrieval_policy_ref, self.run.rerank_policy_ref,
            self.run.top_k, "NOT_APPLICABLE", "NOT_APPLICABLE", "RUNNING",
            (), False, None, self.run.job_id, self.run.trace_id, 0,
            self.now, None,
        )
        service, _guard = self.service(run=running)
        for method, code in (
            (service.get_result, "RAG_RETRIEVAL_RESULT_NOT_READY"),
            (service.get_context, "RAG_CONTEXT_NOT_READY"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(RAGRetrievalReadError) as caught:
                    method(self.query)
                self.assertEqual(caught.exception.code, code)

    def test_missing_session_and_missing_projection_fail_closed(self):
        service = RAGRetrievalReadService(
            unit_of_work=Tx, access=Access(None), license_guard=Guard(),
            authorization=Authorization(self.actor, self.project, "PROJECT_MANAGER"),
            repository=Repository(self.run, self.result, self.context),
            clock=lambda: self.now,
        )
        with self.assertRaises(RAGRetrievalReadError) as caught:
            service.get_run(self.query)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        service, _guard = self.service(role="PROJECT_MANAGER", run=False)
        with self.assertRaises(RAGRetrievalReadError) as caught:
            service.get_run(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
