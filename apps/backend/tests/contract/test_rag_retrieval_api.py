from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.rag.api.retrieval_runs import create_rag_retrieval_router
from plm_assistant.modules.rag.application.create_retrieval import (
    CreatedProjectRetrieval,
    RAGRetrievalCreateError,
)
from plm_assistant.modules.rag.application.retrieval_read import (
    RAGContextBundleView,
    RAGContextItemView,
    RAGRetrievalCandidateView,
    RAGRetrievalReadError,
    RAGRetrievalResultView,
    RAGRetrievalRunView,
    RAGRetrievalScorePartView,
)


ORIGIN = "https://plm.example.test"


class Sessions:
    def __init__(self): self.valid = True

    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (not self.valid or token != b"a" * 32 or csrf_token != b"c" * 32
                or require_csrf is not True):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Creates:
    def __init__(self, value): self.value, self.command = value, None

    def create(self, command):
        self.command = command
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class Reads:
    def __init__(self, run, result, context):
        self.run, self.result, self.context = run, result, context

    @staticmethod
    def _value(value):
        if isinstance(value, Exception):
            raise value
        return value

    def get_run(self, _query): return self._value(self.run)
    def get_result(self, _query): return self._value(self.result)
    def get_context(self, _query): return self._value(self.context)


class RAGRetrievalApiTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, tzinfo=timezone.utc)
        self.project, self.run_id, self.job, self.creator = (
            uuid.uuid4() for _ in range(4)
        )
        self.index, self.trace = uuid.uuid4(), uuid.uuid4()
        self.created = CreatedProjectRetrieval(
            self.run_id, self.job, self.project, b"q" * 32,
        )
        self.run = RAGRetrievalRunView(
            self.run_id, self.project, self.creator, None, self.index,
            "fts.project.v1", "none.v1", 5, "NOT_APPLICABLE",
            "NOT_APPLICABLE", "SUCCEEDED", ("CANDIDATE_SHORTFALL",),
            False, None, self.job, self.trace, 1, self.now, self.now,
        )
        self.score = RAGRetrievalScorePartView(
            "FINAL", 1, 900_000, 900_000, 1_000_000, 900_000,
            "fts.project.v1",
        )
        self.candidate = RAGRetrievalCandidateView(
            uuid.uuid4(), 0, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            "PROJECT_RECORD", {"locator_type": "PAGE", "page": 2},
            "FTS", 900_000, (self.score,), "最小上下文",
        )
        self.result = RAGRetrievalResultView(
            self.run_id, self.project, (self.candidate,),
            ("CANDIDATE_SHORTFALL",), False, self.now,
        )
        item = RAGContextItemView(
            0, self.candidate.chunk_id, self.candidate.document_version_ref,
            dict(self.candidate.source_locator), 0, 5, 5, "最小上下文",
        )
        self.context = RAGContextBundleView(
            uuid.uuid4(), self.run_id, self.project, "project-documents.v1",
            b"b" * 32, 1000, 5, (item,), self.now,
        )
        self.sessions = Sessions()
        self.creates = Creates(self.created)
        self.reads = Reads(self.run, self.result, self.context)
        self.base = f"/api/v1/projects/{self.project}/retrieval-runs"
        self.headers = {
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "RAG-HTTP-00000001",
            "origin": ORIGIN,
            "host": "plm.example.test",
        }
        self.body = {
            "query": "PLM 实施范围",
            "metadata_filter": {"source_type": ["PROJECT_RECORD"]},
            "project_index_ref": str(self.index),
            "global_index_ref": None,
            "retrieval_policy_ref": "fts.project.v1",
            "rerank_policy_ref": "none.v1",
            "top_k": 5,
        }

    def client(self):
        router = create_rag_retrieval_router(
            sessions=self.sessions, creates=self.creates, reads=self.reads,
            origins=LoginOriginPolicy([ORIGIN]),
        )
        return TestClient(create_app(rag_retrieval_router=router), base_url=ORIGIN)

    def test_default_closed_and_strict_create_returns_safe_202(self):
        with TestClient(create_app(), base_url=ORIGIN) as closed:
            self.assertEqual(closed.post(
                self.base, json=self.body, headers=self.headers,
            ).status_code, 404)
        with self.client() as client:
            response = client.post(self.base, json=self.body, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["location"], self.base + "/" + str(self.run_id))
        self.assertEqual(response.json()["data"], {
            "retrieval_run_id": str(self.run_id), "job_id": str(self.job),
        })
        self.assertEqual(self.creates.command.project_id, self.project)
        self.assertEqual(self.creates.command.idempotency_key, "RAG-HTTP-00000001")
        self.assertEqual(self.creates.command.query, self.body["query"])
        self.assertNotIn("fingerprint", response.text.lower())

    def test_create_rejects_extra_fields_noncanonical_policy_and_security_drift(self):
        cases = (
            ({**self.body, "api_key": "forbidden"}, self.headers, 400),
            ({**self.body, "global_index_ref": str(uuid.uuid4())}, self.headers, 422),
            ({**self.body, "retrieval_policy_ref": "vector.v1"}, self.headers, 422),
            ({**self.body, "top_k": True}, self.headers, 422),
            (self.body, {**self.headers, "origin": "https://evil.test"}, 403),
            (self.body, {key: value for key, value in self.headers.items()
                         if key != "idempotency-key"}, 422),
        )
        with self.client() as client:
            for body, headers, status in cases:
                with self.subTest(status=status, body=body):
                    self.assertEqual(client.post(
                        self.base, json=body, headers=headers,
                    ).status_code, status)
            self.assertEqual(client.post(
                self.base + "?x=1", json=self.body, headers=self.headers,
            ).status_code, 400)
            duplicate = '{"query":"one","query":"two"}'
            self.assertEqual(client.post(
                self.base, content=duplicate,
                headers={**self.headers, "content-type": "application/json"},
            ).status_code, 400)

    def test_run_result_and_context_are_minimized(self):
        headers = {"cookie": self.headers["cookie"], "host": "plm.example.test"}
        with self.client() as client:
            run = client.get(self.base + "/" + str(self.run_id), headers=headers)
            result = client.get(
                self.base + "/" + str(self.run_id) + "/result", headers=headers,
            )
            context = client.get(
                self.base + "/" + str(self.run_id) + "/context", headers=headers,
            )
        self.assertEqual((run.status_code, result.status_code, context.status_code),
                         (200, 200, 200))
        self.assertEqual(run.headers["etag"], '"v1"')
        self.assertEqual(result.json()["data"]["candidates"][0]["snippet"],
                         "最小上下文")
        self.assertEqual(context.json()["data"]["items"][0]["snippet"],
                         "最小上下文")
        self.assertEqual(context.json()["data"]["bundle_fingerprint"], "62" * 32)
        run_data = run.json()["data"]
        for forbidden in ("query", "filter", "fingerprint", "cipher", "vector"):
            self.assertNotIn(forbidden, run_data)
        for response in (run, result, context):
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn("golden", response.text.lower())
            self.assertNotIn("answer", response.text.lower())

    def test_safe_create_and_read_error_mapping(self):
        with self.client() as client:
            for code, status in (
                ("RESOURCE_NOT_FOUND", 404),
                ("LICENSE_OPERATION_DENIED", 403),
                ("PROJECT_ARCHIVED", 409),
                ("CONFLICT_IDEMPOTENCY", 409),
                ("RAG_METADATA_FILTER_NOT_ALLOWED", 422),
                ("RAG_RETRIEVAL_UNAVAILABLE", 503),
            ):
                with self.subTest(create=code):
                    self.creates.value = RAGRetrievalCreateError(code)
                    self.assertEqual(client.post(
                        self.base, json=self.body, headers=self.headers,
                    ).status_code, status)
            self.creates.value = self.created
            for code, status in (
                ("AUTH_ACCESS_DENIED", 401),
                ("RESOURCE_NOT_FOUND", 404),
                ("LICENSE_OPERATION_DENIED", 403),
                ("RAG_RETRIEVAL_RESULT_NOT_READY", 409),
                ("RAG_RETRIEVAL_READ_UNAVAILABLE", 503),
            ):
                with self.subTest(read=code):
                    self.reads.run = RAGRetrievalReadError(code)
                    self.assertEqual(client.get(
                        self.base + "/" + str(self.run_id),
                        headers={"cookie": self.headers["cookie"]},
                    ).status_code, status)

    def test_invalid_projection_and_query_are_not_exposed(self):
        self.reads.run = RAGRetrievalRunView(
            self.run_id, uuid.uuid4(), self.creator, None, self.index,
            "fts.project.v1", "none.v1", 5, "NOT_APPLICABLE",
            "NOT_APPLICABLE", "SUCCEEDED", (), False, None, self.job,
            self.trace, 1, self.now, self.now,
        )
        with self.client() as client:
            response = client.get(
                self.base + "/" + str(self.run_id),
                headers={"cookie": self.headers["cookie"]},
            )
            query = client.get(
                self.base + "/" + str(self.run_id) + "?x=1",
                headers={"cookie": self.headers["cookie"]},
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.project), response.text)
        self.assertEqual(query.status_code, 400)


if __name__ == "__main__":
    unittest.main()
