from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.trace.api.revoke_link import create_trace_revoke_router
from plm_assistant.modules.trace.application.revoke_link import (
    RevokedTraceLink, TraceRevokeError,
)


class _Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class _Revokes:
    def __init__(self, project, link):
        self.project, self.link = project, link
        self.calls = 0
        self.error = None
        self.forged = False

    def revoke(self, command, *, idempotency_key):
        self.calls += 1
        assert command.project_id == self.project
        assert command.trace_link_id == self.link
        assert command.expected_version == 0
        assert command.session_token == b"s" * 32
        assert command.csrf_token == b"c" * 32
        assert idempotency_key == "trace-revoke-http-key-001"
        if self.error:
            raise TraceRevokeError(self.error)
        return RevokedTraceLink(uuid.uuid4() if self.forged else self.link, 1)


class TraceRevokeApiTests(unittest.TestCase):
    def setUp(self):
        self.project, self.link = uuid.uuid4(), uuid.uuid4()
        self.revokes = _Revokes(self.project, self.link)
        router = create_trace_revoke_router(
            sessions=_Sessions(), revokes=self.revokes,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(trace_revoke_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.project}"
                     f"/trace-links/{self.link}:revoke")
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "if-match": '"v0"',
            "idempotency-key": "trace-revoke-http-key-001",
        }

    def test_default_closed_and_minimal_success(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path, headers=self.headers).status_code, 404)
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"], {
            "trace_link_id": str(self.link), "link_state": "REVOKED",
        })
        self.assertIn("trace_id", response.json())
        self.assertEqual(self.revokes.calls, 1)

    def test_security_version_key_body_and_query_preconditions(self):
        for missing, expected in (
            ("origin", 403), ("cookie", 401), ("x-csrf-token", 403),
            ("if-match", 428), ("idempotency-key", 422),
        ):
            headers = {key: value for key, value in self.headers.items()
                       if key != missing}
            with self.subTest(missing=missing):
                self.assertEqual(self.client.post(self.path, headers=headers).status_code,
                                 expected)
        for headers, expected in (
            ({**self.headers, "if-match": 'W/"v0"'}, 400),
            ({**self.headers, "origin": "https://evil.example.test"}, 403),
            ({**self.headers, "host": "evil.example.test"}, 403),
        ):
            self.assertEqual(self.client.post(self.path, headers=headers).status_code,
                             expected)
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          content=b"{}").status_code, 400)
        self.assertEqual(self.client.post(self.path + "?extra=1",
                                          headers=self.headers).status_code, 400)
        self.assertEqual(self.revokes.calls, 0)

    def test_safe_application_errors_and_forged_result(self):
        for code, expected in (
            ("AUTH_ACCESS_DENIED", 401), ("RESOURCE_NOT_FOUND", 404),
            ("PROJECT_ARCHIVED", 409), ("CONFLICT_VERSION", 409),
            ("CONFLICT_STATE", 409), ("CONFLICT_IDEMPOTENCY", 409),
            ("LICENSE_OPERATION_DENIED", 403), ("TRACE_UNAVAILABLE", 503),
        ):
            self.revokes.error = code
            with self.subTest(code=code):
                response = self.client.post(self.path, headers=self.headers)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("Traceback", response.text)
        self.revokes.error = None
        self.revokes.forged = True
        self.assertEqual(self.client.post(self.path, headers=self.headers).status_code, 503)


if __name__ == "__main__":
    unittest.main()
