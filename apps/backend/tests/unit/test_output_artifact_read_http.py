from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.output.api.read_artifact import (
    create_output_artifact_read_router,
)
from plm_assistant.modules.output.application.read_artifact import (
    OutputArtifactReadError, OutputArtifactReference,
)
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers


class Sessions:
    def __init__(self):
        self.error = None
        self.calls = []
    def validate(self, token):
        self.calls.append(token)
        if self.error:
            raise self.error


class Origins:
    def require_trusted_host(self, headers):
        del headers


class Service:
    def __init__(self, result):
        self.result, self.calls = result, []
    def get_available(self, query, *, project_id, output_request_id):
        self.calls.append((query, project_id, output_request_id))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class OutputArtifactReadHttpTests(unittest.TestCase):
    def setUp(self):
        self.project, self.request = uuid.uuid4(), uuid.uuid4()
        self.trace = uuid.uuid4()
        self.token = bytes.fromhex("77" * 32)
        self.value = OutputArtifactReference(
            uuid.uuid4(), self.request, self.project, uuid.uuid4(), uuid.uuid4(),
            "DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "cd" * 32, 512,
        )
        self.sessions, self.service = Sessions(), Service(self.value)
        app = FastAPI()
        @app.middleware("http")
        async def tracing(request, call_next):
            request.state.trace_id = str(self.trace)
            return await call_next(request)
        app.include_router(create_output_artifact_read_router(
            sessions=self.sessions, origins=Origins(), service=self.service,
        ))
        install_error_handlers(app)
        self.client = TestClient(app)

    def _get(self, query=""):
        return self.client.get(
            f"/api/v1/projects/{self.project}/output-requests/{self.request}/artifact{query}",
            headers={"origin": "https://plm.example.test",
                     "cookie": f"plm_session={self.token.hex()}"},
        )

    def test_returns_fixed_reference_and_controlled_document_content_route(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["output_artifact_id"], str(self.value.output_artifact_id))
        self.assertEqual(data["document_version_id"], str(self.value.document_version_id))
        self.assertEqual(data["content_url"],
            f"/api/v1/projects/{self.project}/documents/{self.value.document_id}"
            f"/versions/{self.value.document_version_id}/content")
        self.assertNotIn("storage_locator", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.sessions.calls, [self.token])

    def test_rejects_query_and_expired_session(self):
        self.assertEqual(self._get("?path=x").status_code, 400)
        self.sessions.error = SessionError("AUTH_SESSION_EXPIRED")
        self.assertEqual(self._get().status_code, 401)

    def test_missing_artifact_is_safe_404(self):
        self.service.result = OutputArtifactReadError("RESOURCE_NOT_FOUND")
        response = self._get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "RESOURCE_NOT_FOUND")

    def test_wrong_projection_fails_closed(self):
        self.service.result = SimpleNamespace()
        self.assertEqual(self._get().status_code, 503)


if __name__ == "__main__":
    unittest.main()
