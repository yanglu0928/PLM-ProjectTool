from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.output.api.create_request import (
    _create_command,
    create_output_request_create_router,
)
from plm_assistant.modules.output.application.create_request import (
    CreatedOutputRequest,
    OutputRequestError,
)
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers
from plm_assistant.modules.platform.application.errors import ApplicationError


class Sessions:
    def __init__(self, user_id=None, error=None):
        self.user_id = user_id or uuid.uuid4()
        self.error = error
        self.calls = []

    def validate(self, token, *, csrf_token=None, require_csrf=False):
        self.calls.append((token, csrf_token, require_csrf))
        if self.error:
            raise self.error
        return SimpleNamespace(user_id=self.user_id)


class Origins:
    def __init__(self, error=None):
        self.error = error

    def require_trusted(self, headers):
        del headers
        if self.error:
            raise self.error


class Service:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.received = None

    def create(self, command, *, idempotency_key):
        self.received = (command, idempotency_key)
        if self.error:
            raise self.error
        return self.result


class OutputRequestCreateHttpTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.template_id = uuid.uuid4()
        self.source_id = uuid.uuid4()
        self.request_id = uuid.uuid4()
        self.job_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.token = bytes.fromhex("11" * 32)
        self.csrf = bytes.fromhex("22" * 32)
        self.trace_id = uuid.uuid4()
        self.idempotency_key = "0123456789abcdef0123456789abcdef"
        self.body = {
            "output_type": "DOCX",
            "template_version_ref": str(self.template_id),
            "source_version_refs": [str(self.source_id)],
            "output_policy_ref": "output.policy.requirement-docx.v1",
            "plugin_operation": "word.generate",
        }
        self.sessions = Sessions(self.user_id)
        self.origins = Origins()
        self.service = Service(CreatedOutputRequest(
            self.request_id, self.project_id, self.job_id, "QUEUED", 202,
        ))
        app = FastAPI()

        @app.middleware("http")
        async def trace(request, call_next):
            request.state.trace_id = str(self.trace_id)
            return await call_next(request)

        app.include_router(create_output_request_create_router(
            sessions=self.sessions,
            origins=self.origins,
            service=self.service,
        ))
        install_error_handlers(app)
        self.client = TestClient(app)

    def _headers(self):
        return {
            "origin": "https://plm.example.test",
            "cookie": f"plm_session={self.token.hex()}",
            "x-csrf-token": self.csrf.hex(),
            "idempotency-key": self.idempotency_key,
        }

    def test_create_returns_only_minimal_202_request_and_job_refs(self):
        response = self.client.post(
            f"/api/v1/projects/{self.project_id}/output-requests",
            headers=self._headers(), json=self.body,
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"], {
            "output_request_id": str(self.request_id),
            "job_id": str(self.job_id),
            "state": "QUEUED",
        })
        self.assertEqual(response.headers["cache-control"], "no-store")
        command, key = self.service.received
        self.assertEqual(key, self.idempotency_key)
        self.assertEqual(command.session_token, self.token)
        self.assertEqual(command.csrf_token, self.csrf)
        self.assertEqual(command.project_id, self.project_id)
        self.assertEqual(command.source_version_refs, (self.source_id,))
        self.assertEqual(self.sessions.calls, [(self.token, self.csrf, True)])

    def test_unknown_or_duplicate_source_fields_are_rejected_before_owner(self):
        unknown = dict(self.body, absolute_path="D:/customer")
        response = self.client.post(
            f"/api/v1/projects/{self.project_id}/output-requests",
            headers=self._headers(), json=unknown,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.service.received)
        duplicate = dict(self.body, source_version_refs=[
            str(self.source_id), str(self.source_id),
        ])
        response = self.client.post(
            f"/api/v1/projects/{self.project_id}/output-requests",
            headers=self._headers(), json=duplicate,
        )
        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.service.received)

    def test_session_and_resolver_errors_use_safe_codes(self):
        self.sessions.error = SessionError("AUTH_SESSION_EXPIRED")
        response = self.client.post(
            f"/api/v1/projects/{self.project_id}/output-requests",
            headers=self._headers(), json=self.body,
        )
        self.assertEqual(response.status_code, 401)
        self.sessions.error = None
        self.service.error = OutputRequestError("VALIDATION_FAILED")
        response = self.client.post(
            f"/api/v1/projects/{self.project_id}/output-requests",
            headers=self._headers(), json=self.body,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_FAILED")

    def test_invalid_command_shape_is_rejected(self):
        with self.assertRaisesRegex(ApplicationError, "REQUEST_MALFORMED"):
            _create_command(
                dict(self.body, extra="field"), token=self.token, csrf=self.csrf,
                project_id=self.project_id, trace_id=self.trace_id,
            )


if __name__ == "__main__":
    unittest.main()
