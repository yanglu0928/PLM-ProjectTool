"""Frozen WORKFLOW_START HTTP contract without implicit production mounting."""

import unittest
import uuid
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.workflow.api.start_workflow import create_workflow_start_router
from plm_assistant.modules.workflow.application.start_workflow import WorkflowStartError
from unit.test_workflow_start_service import initial_view


class WorkflowStartApiTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.view = initial_view(self.project_id)
        self.result = self.view
        self.calls = []
        self.sessions = SimpleNamespace(validate=lambda *_args, **_kwargs: None)
        self.workflows = SimpleNamespace(start=self.start)
        self.router = create_workflow_start_router(
            sessions=self.sessions, workflows=self.workflows,
            origins=LoginOriginPolicy(["http://localhost"]),
        )
        self.path = f"/api/v1/projects/{self.project_id}/workflow:start"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "workflow-start-key-1234",
            "if-match": '"v0"',
            "origin": "http://localhost",
        }

    def start(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def request(self, *, headers=None, path=None, content=None):
        with TestClient(create_app(workflow_start_router=self.router),
                        base_url="http://localhost") as client:
            return client.post(path or self.path, headers=headers or self.headers,
                               content=content)

    def test_opt_in_200_and_first_result_projection(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"]["state"], "ACTIVE")
        self.assertEqual(response.json()["data"]["current_stage"], "HANDOVER")
        self.assertEqual(len(response.json()["data"]["stages"]), 6)
        self.assertEqual(set(response.json()["data"]), {
            "workflow_id", "version", "state", "current_stage", "stages", "etag",
        })
        candidate, key = self.calls[0]
        self.assertEqual(candidate.project_id, self.project_id)
        self.assertEqual(candidate.expected_version, 0)
        self.assertEqual(key, self.headers["idempotency-key"])
        self.assertEqual(str(candidate.trace_id), response.json()["trace_id"])

    def test_default_application_does_not_mount_start(self):
        with TestClient(create_app(), base_url="http://localhost") as client:
            self.assertEqual(client.post(self.path, headers=self.headers).status_code, 404)

    def test_request_preconditions_reject_before_service(self):
        variants = (
            ({k: v for k, v in self.headers.items() if k != "cookie"}, self.path, None, 401),
            ({k: v for k, v in self.headers.items() if k != "x-csrf-token"}, self.path, None, 403),
            ({k: v for k, v in self.headers.items() if k != "idempotency-key"}, self.path, None, 422),
            ({k: v for k, v in self.headers.items() if k != "if-match"}, self.path, None, 428),
            (self.headers | {"if-match": 'W/"v0"'}, self.path, None, 400),
            (self.headers | {"host": "evil.invalid"}, self.path, None, 403),
            (self.headers, self.path + "?extra=1", None, 400),
            (self.headers, self.path, b"{}", 400),
        )
        for headers, path, content, status in variants:
            with self.subTest(status=status, path=path):
                self.assertEqual(self.request(headers=headers, path=path,
                                              content=content).status_code, status)
        self.assertEqual(self.calls, [])

    def test_service_error_map_and_private_failure_hidden(self):
        for error, code, status in (
            (WorkflowStartError("RESOURCE_NOT_FOUND"), "RESOURCE_NOT_FOUND", 404),
            (WorkflowStartError("AUTH_ACCESS_DENIED"), "AUTH_SESSION_EXPIRED", 401),
            (WorkflowStartError("CONFLICT_VERSION"), "CONFLICT_VERSION", 409),
            (WorkflowStartError("CONFLICT_STATE"), "CONFLICT_STATE", 409),
            (WorkflowStartError("CONFLICT_IDEMPOTENCY"), "CONFLICT_IDEMPOTENCY", 409),
            (WorkflowStartError("PROJECT_ARCHIVED"), "PROJECT_ARCHIVED", 409),
            (WorkflowStartError("LICENSE_OPERATION_DENIED"), "LICENSE_OPERATION_DENIED", 403),
            (RuntimeError("private workflow data"), "SYSTEM_UNAVAILABLE", 503),
        ):
            self.result = error
            with self.subTest(code=code):
                response = self.request()
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertNotIn("private workflow data", response.text)

    def test_foreign_or_current_noninitial_view_is_rejected(self):
        for view in (replace(self.view, project_id=uuid.uuid4()),
                     replace(self.view, lock_version=2)):
            self.result = view
            with self.subTest(view=view):
                self.assertEqual(self.request().status_code, 503)

    def test_expired_session_never_calls_start(self):
        def expired(*_args, **_kwargs):
            raise SessionError("AUTH_SESSION_EXPIRED")
        self.sessions.validate = expired
        self.assertEqual(self.request().status_code, 401)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
