from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.trace.api.supersede_link import create_trace_supersede_router
from plm_assistant.modules.trace.application.supersede_link import (
    SupersededTraceLink, TraceSupersedeError,
)


class _Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class _Supersedes:
    def __init__(self, project, link, source, target):
        self.project, self.link = project, link
        self.source, self.target = source, target
        self.new_id = uuid.uuid4()
        self.calls = 0
        self.error = None
        self.forged = False

    def supersede_refs(self, command, *, idempotency_key):
        self.calls += 1
        assert command.project_id == self.project
        assert command.trace_link_id == self.link
        assert command.expected_version == 0
        assert command.session_token == b"s" * 32
        assert command.csrf_token == b"c" * 32
        assert command.source.resource_type == "DOC-02"
        assert command.source.resource_id == self.source[0]
        assert command.source.version_id == self.source[1]
        assert command.target.resource_id == self.target[0]
        assert command.target.version_id == self.target[1]
        assert command.relation_type == "IMPLEMENTS"
        assert idempotency_key == "trace-supersede-http-001"
        if self.error:
            raise TraceSupersedeError(self.error)
        return SupersededTraceLink(
            uuid.uuid4() if self.forged else self.link, self.new_id, 1,
        )


class TraceSupersedeApiTests(unittest.TestCase):
    def setUp(self):
        self.project, self.link = uuid.uuid4(), uuid.uuid4()
        self.source = (uuid.uuid4(), uuid.uuid4())
        self.target = (uuid.uuid4(), uuid.uuid4())
        self.supersedes = _Supersedes(self.project, self.link,
                                     self.source, self.target)
        router = create_trace_supersede_router(
            sessions=_Sessions(), supersedes=self.supersedes,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(trace_supersede_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.project}"
                     f"/trace-links/{self.link}:supersede")
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "if-match": '"v0"',
            "idempotency-key": "trace-supersede-http-001",
        }
        self.body = {
            "source": {"resource_type": "DOC-02",
                       "resource_id": str(self.source[0]),
                       "version_id": str(self.source[1])},
            "target": {"resource_type": "DOC-02",
                       "resource_id": str(self.target[0]),
                       "version_id": str(self.target[1])},
            "relation_type": "IMPLEMENTS",
        }

    def test_default_closed_and_minimal_created_result(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path, headers=self.headers,
                                       json=self.body).status_code, 404)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.json()["data"], {
            "trace_link_id": str(self.supersedes.new_id),
        })
        self.assertIn("trace_id", response.json())
        self.assertEqual(self.supersedes.calls, 1)

    def test_auth_version_key_body_and_query_preconditions(self):
        for missing, expected in (
            ("origin", 403), ("cookie", 401), ("x-csrf-token", 403),
            ("if-match", 428), ("idempotency-key", 422),
        ):
            headers = {key: value for key, value in self.headers.items()
                       if key != missing}
            with self.subTest(missing=missing):
                self.assertEqual(self.client.post(self.path, headers=headers,
                                                  json=self.body).status_code,
                                 expected)
        for headers, expected in (
            ({**self.headers, "if-match": 'W/"v0"'}, 400),
            ({**self.headers, "origin": "https://evil.example.test"}, 403),
            ({**self.headers, "host": "evil.example.test"}, 403),
        ):
            self.assertEqual(self.client.post(self.path, headers=headers,
                                              json=self.body).status_code,
                             expected)
        self.assertEqual(self.client.post(self.path + "?extra=1",
                                          headers=self.headers,
                                          json=self.body).status_code, 400)
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          content=b"{}").status_code, 400)
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          content=b'{"source":1,"source":2}').status_code,
                         400)
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          json=self.body | {"owner_module": "document"}
                                          ).status_code, 400)
        malformed_ref = self.body | {"source": self.body["source"] | {"scope": "PROJECT"}}
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          json=malformed_ref).status_code, 400)
        self.assertEqual(self.supersedes.calls, 0)

    def test_safe_application_errors_and_forged_result(self):
        for code, expected in (
            ("AUTH_ACCESS_DENIED", 401), ("RESOURCE_NOT_FOUND", 404),
            ("PROJECT_ARCHIVED", 409), ("CONFLICT_VERSION", 409),
            ("CONFLICT_STATE", 409), ("CONFLICT_IDEMPOTENCY", 409),
            ("LICENSE_OPERATION_DENIED", 403), ("TRACE_UNAVAILABLE", 503),
        ):
            self.supersedes.error = code
            with self.subTest(code=code):
                response = self.client.post(self.path, headers=self.headers,
                                            json=self.body)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("Traceback", response.text)
        self.supersedes.error = None
        self.supersedes.forged = True
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          json=self.body).status_code, 503)


if __name__ == "__main__":
    unittest.main()
