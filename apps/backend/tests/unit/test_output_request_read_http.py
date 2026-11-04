from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.output.api.read_request import (
    create_output_request_read_router, output_request_view_data,
)
from plm_assistant.modules.output.application.read_request import (
    OutputRequestReadError, OutputRequestReadQuery, OutputRequestReadService,
    OutputRequestView,
)
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers


class Sessions:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def validate(self, token):
        self.calls.append(token)
        if self.error:
            raise self.error


class Origins:
    def require_trusted_host(self, headers):
        del headers


class ReadService:
    def __init__(self, view=None, error=None):
        self.view, self.error, self.received = view, error, None

    def get(self, query, *, project_id, output_request_id):
        self.received = (query, project_id, output_request_id)
        if self.error:
            raise self.error
        return self.view


class OutputRequestReadHttpTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.request_id = uuid.uuid4()
        self.token = bytes.fromhex("31" * 32)
        self.trace_id = uuid.uuid4()
        self.view = OutputRequestView(
            output_request_id=self.request_id, project_id=self.project_id,
            output_type="DOCX", template_version_ref=uuid.uuid4(),
            source_version_refs=(uuid.uuid4(),), output_policy_ref="output.policy.v1",
            plugin_operation="word.generate", context_snapshot_ref=uuid.uuid4(),
            context_fingerprint=bytes.fromhex("ab" * 32), request_state="QUEUED",
            job_ref=uuid.uuid4(), execution_ref=None, generation_no=1,
            requested_at=datetime(2026, 11, 4, tzinfo=timezone.utc),
            completed_at=None, lock_version=2,
        )
        self.sessions = Sessions()
        self.service = ReadService(self.view)
        app = FastAPI()

        @app.middleware("http")
        async def trace(request, call_next):
            request.state.trace_id = str(self.trace_id)
            return await call_next(request)

        app.include_router(create_output_request_read_router(
            sessions=self.sessions, origins=Origins(), service=self.service,
        ))
        install_error_handlers(app)
        self.client = TestClient(app)

    def _get(self, suffix=""):
        return self.client.get(
            f"/api/v1/projects/{self.project_id}/output-requests/{self.request_id}{suffix}",
            headers={"origin": "https://plm.example.test",
                     "cookie": f"plm_session={self.token.hex()}"},
        )

    def test_get_returns_fixed_refs_and_safe_minimal_projection(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["output_request_id"], str(self.request_id))
        self.assertEqual(data["project_id"], str(self.project_id))
        self.assertEqual(data["source_version_refs"],
                         [str(self.view.source_version_refs[0])])
        self.assertEqual(data["context_fingerprint"], "ab" * 32)
        self.assertEqual(data["state"], "QUEUED")
        self.assertEqual(response.headers["etag"], '"v2"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        body = response.text.lower()
        for forbidden in ("context_payload", "secret", "absolute_path",
                          "idempotency_key", "storage_locator"):
            self.assertNotIn(forbidden, body)
        query, project_id, request_id = self.service.received
        self.assertEqual(query, OutputRequestReadQuery(self.token, self.trace_id))
        self.assertEqual((project_id, request_id), (self.project_id, self.request_id))
        self.assertEqual(self.sessions.calls, [self.token])

    def test_get_has_no_csrf_or_idempotency_requirement_and_rejects_query(self):
        response = self._get("?unexpected=1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.sessions.calls, [self.token])
        self.assertIsNone(self.service.received)

    def test_expired_session_and_missing_resource_are_safe(self):
        self.sessions.error = SessionError("AUTH_SESSION_EXPIRED")
        response = self._get()
        self.assertEqual(response.status_code, 401)
        self.sessions.error = None
        self.service.error = OutputRequestReadError("RESOURCE_NOT_FOUND")
        response = self._get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "RESOURCE_NOT_FOUND")

    def test_projection_does_not_accept_wrong_type(self):
        with self.assertRaises(Exception):
            output_request_view_data(SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
