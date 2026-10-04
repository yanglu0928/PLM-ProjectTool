from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.rag.api.retrieval_cancel import (
    create_rag_retrieval_cancel_router,
)
from plm_assistant.modules.rag.application.retrieval_cancel import (
    CancelledRAGRetrieval,
    RAGRetrievalCancelError,
)


ORIGIN = "https://plm.example.test"


class Sessions:
    def __init__(self): self.valid = True
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (not self.valid or token != b"s" * 32 or csrf_token != b"c" * 32
                or require_csrf is not True):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Cancellations:
    def __init__(self, result): self.result, self.command = result, None
    def cancel_retrieval(self, command, *, idempotency_key):
        self.command = command
        if isinstance(self.result, Exception): raise self.result
        return self.result


class RAGRetrievalCancelApiTests(unittest.TestCase):
    def setUp(self):
        self.run, self.job, self.project = (
            uuid.uuid4() for _ in range(3)
        )
        self.result = CancelledRAGRetrieval(
            self.run, self.job, self.project, "CANCEL_REQUESTED", True,
            0, 2, None,
        )
        self.sessions = Sessions()
        self.cancellations = Cancellations(self.result)
        self.path = (
            f"/api/v1/projects/{self.project}/retrieval-runs/"
            f"{self.run}:cancel"
        )
        self.headers = {
            "origin": ORIGIN,
            "host": "plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "RAG-CANCEL-000001",
            "if-match": '"v0"',
        }

    def client(self):
        router = create_rag_retrieval_cancel_router(
            sessions=self.sessions, cancellations=self.cancellations,
            origins=LoginOriginPolicy([ORIGIN]),
        )
        return TestClient(
            create_app(rag_retrieval_cancel_router=router),
            base_url=ORIGIN,
        )

    def post(self, client, **headers):
        return client.post(
            self.path, json={"reason": "用户取消本次检索"},
            headers=self.headers | headers,
        )

    def test_default_closed_and_safe_response(self):
        with TestClient(create_app(), base_url=ORIGIN) as client:
            self.assertEqual(self.post(client).status_code, 404)
        with self.client() as client:
            response = self.post(client)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.json()["data"], {
            "retrieval_run_id": str(self.run), "job_id": str(self.job),
            "state": "CANCEL_REQUESTED", "changed": True,
            "etag": '"v0"',
            "status_url": (
                f"/api/v1/projects/{self.project}/retrieval-runs/{self.run}"
            ),
        })
        self.assertEqual(self.cancellations.command.expected_version, 0)
        self.assertEqual(self.cancellations.command.reason, "用户取消本次检索")

    def test_strict_security_and_body(self):
        with self.client() as client:
            cases = (
                ({"origin": "https://evil.test"}, 403),
                ({"if-match": "*"}, 400),
                ({"idempotency-key": "short"}, 422),
                ({"cookie": "plm_session=bad"}, 401),
            )
            for headers, status in cases:
                with self.subTest(headers=headers):
                    self.assertEqual(self.post(client, **headers).status_code, status)
            self.assertEqual(client.post(
                self.path, json={}, headers=self.headers,
            ).status_code, 400)
            self.assertEqual(client.post(
                self.path + "?x=1", json={"reason": "x"},
                headers=self.headers,
            ).status_code, 400)

    def test_safe_error_mapping_and_response_binding(self):
        with self.client() as client:
            for code, status in (
                ("RESOURCE_NOT_FOUND", 404),
                ("LICENSE_OPERATION_DENIED", 403),
                ("CONFLICT_VERSION", 409),
                ("CONFLICT_IDEMPOTENCY", 409),
                ("VALIDATION_FAILED", 422),
                ("RAG_RETRIEVAL_CANCEL_UNAVAILABLE", 503),
            ):
                with self.subTest(code=code):
                    self.cancellations.result = RAGRetrievalCancelError(code)
                    self.assertEqual(self.post(client).status_code, status)
            self.cancellations.result = CancelledRAGRetrieval(
                uuid.uuid4(), self.job, self.project, "CANCELLED", True,
                1, 2, datetime.now(timezone.utc),
            )
            self.assertEqual(self.post(client).status_code, 503)


if __name__ == "__main__":
    unittest.main()
