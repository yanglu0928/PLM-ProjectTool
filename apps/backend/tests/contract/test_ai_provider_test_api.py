from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.submit_provider_test import create_ai_provider_test_router
from plm_assistant.modules.ai.application.submit_provider_test import (
    AIProviderTestSubmitError, SubmitAIProviderTest,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobRef


class Sessions:
    valid = True

    def validate(self, token, *, csrf_token, require_csrf):
        if not self.valid or token != b"a" * 32 or csrf_token != b"c" * 32 or not require_csrf:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Submitter:
    def __init__(self):
        self.result = AIProviderTestJobRef(uuid.uuid4(), uuid.uuid4())
        self.last: SubmitAIProviderTest | None = None
        self.failure: str | None = None

    def submit(self, command: SubmitAIProviderTest):
        self.last = command
        if self.failure:
            raise AIProviderTestSubmitError(self.failure)
        return self.result


class AIProviderTestApiTests(unittest.TestCase):
    def setUp(self):
        self.provider_id = uuid.uuid4()
        self.sessions = Sessions()
        self.submitter = Submitter()
        router = create_ai_provider_test_router(
            sessions=self.sessions, providers=self.submitter,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_provider_test_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/admin/ai/providers/{self.provider_id}:test"
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "if-match": '"v0"',
            "idempotency-key": str(uuid.uuid4()),
            "origin": "https://plm.example.test",
        }

    def post(self, *, headers=None, path=None, content=None):
        return self.client.post(path or self.path, headers=self.headers if headers is None else headers,
                                content=content)

    def test_default_closed_and_202_job_ref(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(self.path, headers=self.headers).status_code, 404)
        response = self.post()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"], {"job_id": str(self.submitter.result.job_id)})
        self.assertEqual(response.headers["location"], f"/api/v1/admin/jobs/{self.submitter.result.job_id}")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual(self.submitter.last.provider_id, self.provider_id)
        self.assertEqual(self.submitter.last.expected_lock_version, 0)
        self.assertEqual(self.submitter.last.idempotency_key, self.headers["idempotency-key"])

    def test_preconditions_and_no_body(self):
        for headers, status in (
            ({k: v for k, v in self.headers.items() if k != "if-match"}, 428),
            ({k: v for k, v in self.headers.items() if k != "idempotency-key"}, 422),
            ({**self.headers, "if-match": 'W/"v0"'}, 400),
            ({**self.headers, "idempotency-key": "short"}, 422),
            ({**self.headers, "origin": "https://evil.test"}, 403),
            ({**self.headers, "x-csrf-token": "short"}, 403),
        ):
            with self.subTest(status=status, headers=headers):
                self.assertEqual(self.post(headers=headers).status_code, status)
        self.assertEqual(self.post(content=b"{}").status_code, 400)
        self.assertEqual(self.post(path=self.path + "?unexpected=1").status_code, 400)
        self.assertEqual(self.post(path="/api/v1/admin/ai/providers/" + str(uuid.UUID(int=0)) + ":test").status_code, 404)

    def test_safe_error_mapping(self):
        self.sessions.valid = False
        self.assertEqual(self.post().status_code, 401)
        self.sessions.valid = True
        for failure, status in (
            ("AUTH_ACCESS_DENIED", 404), ("AI_PROVIDER_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("CONFLICT_VERSION", 409),
            ("CONFLICT_IDEMPOTENCY", 409), ("AI_PROVIDER_STATE_CONFLICT", 409),
            ("AI_PROVIDER_SECRET_UNAVAILABLE", 503), ("AI_PROVIDER_POLICY_UNAVAILABLE", 503),
        ):
            with self.subTest(failure=failure):
                self.submitter.failure = failure
                self.assertEqual(self.post().status_code, status)


if __name__ == "__main__":
    unittest.main()
