from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.output.api.list_cursor import OutputRequestListCursorCodec
from plm_assistant.modules.output.api.list_requests import create_output_request_list_router
from plm_assistant.modules.output.application.list_requests import (
    OutputRequestListError, OutputRequestListPage,
)
from plm_assistant.modules.output.application.read_request import OutputRequestView
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers


class Sessions:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def validate(self, token):
        self.calls.append(token)
        if self.error:
            raise self.error


class Origins:
    def require_trusted_host(self, headers):
        del headers


class Service:
    def __init__(self, page):
        self.page, self.query = page, None

    def list_page(self, query):
        self.query = query
        return self.page


class OutputRequestListHttpTests(unittest.TestCase):
    def setUp(self):
        self.project_id, self.request_id = uuid.uuid4(), uuid.uuid4()
        self.token, self.trace_id = bytes.fromhex("52" * 32), uuid.uuid4()
        self.requested_at = datetime(2026, 11, 4, tzinfo=timezone.utc)
        self.view = OutputRequestView(
            output_request_id=self.request_id, project_id=self.project_id,
            output_type="DOCX", template_version_ref=uuid.uuid4(),
            source_version_refs=(uuid.uuid4(),), output_policy_ref="output.policy.v1",
            plugin_operation="word.generate", context_snapshot_ref=uuid.uuid4(),
            context_fingerprint=bytes.fromhex("cd" * 32), request_state="QUEUED",
            job_ref=uuid.uuid4(), execution_ref=None, generation_no=1,
            requested_at=self.requested_at, completed_at=None, lock_version=4,
        )
        self.page = OutputRequestListPage(
            (self.view,), self.requested_at, self.request_id, True,
        )
        self.sessions, self.service = Sessions(), Service(self.page)
        self.cursors = OutputRequestListCursorCodec(bytes.fromhex("79" * 32))
        app = FastAPI()

        @app.middleware("http")
        async def trace(request, call_next):
            request.state.trace_id = str(self.trace_id)
            return await call_next(request)

        app.include_router(create_output_request_list_router(
            sessions=self.sessions, origins=Origins(),
            service=self.service, cursors=self.cursors,
        ))
        install_error_handlers(app)
        self.client = TestClient(app)

    def _get(self, query=""):
        return self.client.get(
            f"/api/v1/projects/{self.project_id}/output-requests{query}",
            headers={"origin": "https://plm.example.test",
                     "cookie": f"plm_session={self.token.hex()}"},
        )

    def test_page_has_fixed_projection_and_scoped_next_cursor_without_csrf(self):
        response = self._get("?page_size=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["output_request_id"], str(self.request_id))
        self.assertTrue(data["has_more"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        after_at, after_id = self.cursors.decode(
            data["next_cursor"], session_token=self.token,
            project_id=self.project_id, page_size=1,
        )
        self.assertEqual((after_at, after_id), (self.requested_at, self.request_id))
        self.assertEqual(self.service.query.page_size, 1)
        self.assertEqual(self.sessions.calls, [self.token])

    def test_unknown_or_duplicate_query_parameters_fail_before_service(self):
        for query in ("?unexpected=1", "?page_size=1&page_size=2", "?page_size=0"):
            response = self._get(query)
            self.assertIn(response.status_code, (400, 422))
        self.assertIsNone(self.service.query)

    def test_expired_session_uses_safe_auth_error(self):
        self.sessions.error = SessionError("AUTH_SESSION_EXPIRED")
        response = self._get()
        self.assertEqual(response.status_code, 401)
        self.assertIsNone(self.service.query)


if __name__ == "__main__":
    unittest.main()
