import uuid
import unittest
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.workflow.api.read_workflow import create_workflow_read_router
from plm_assistant.modules.workflow.application.read_workflow import WorkflowReadError
from unit.test_workflow_read import snapshot


class WorkflowReadApiTests(unittest.TestCase):
    def setUp(self):
        self.view = snapshot()
        self.calls = []
        self.result = self.view
        self.sessions = SimpleNamespace(validate=lambda token: None)
        self.workflows = SimpleNamespace(get=self.get)
        self.router = create_workflow_read_router(sessions=self.sessions, workflows=self.workflows, origins=LoginOriginPolicy(["http://localhost"]))
        self.path = f"/api/v1/projects/{self.view.project_id}/workflow"
        self.headers = {"cookie": "plm_session=" + (b"s"*32).hex()}
    def get(self, query):
        self.calls.append(query)
        if isinstance(self.result, Exception): raise self.result
        return self.result
    def test_opt_in_safe_fields_etag_and_trace(self):
        with TestClient(create_app(workflow_read_router=self.router), base_url="http://localhost") as client:
            response = client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()["data"]
        self.assertEqual(set(data), {"workflow_id", "version", "state", "current_stage", "stages", "etag"})
        self.assertEqual(set(data["stages"][0]), {"stage_key", "order", "state", "checklist_items"})
        self.assertEqual(set(data["stages"][0]["checklist_items"][0]), {"item_key", "required", "state"})
        self.assertEqual(self.calls[0].project_id, self.view.project_id)
        self.assertEqual(str(self.calls[0].trace_id), response.json()["trace_id"])
    def test_missing_cookie_unknown_query_and_untrusted_host_denied(self):
        with TestClient(create_app(workflow_read_router=self.router), base_url="http://localhost") as client:
            self.assertEqual(client.get(self.path).status_code, 401)
            self.assertEqual(client.get(self.path+"?extra=1", headers=self.headers).status_code, 400)
            self.assertEqual(client.get(self.path, headers=self.headers | {"host":"evil.invalid"}).status_code, 403)
        self.assertEqual(self.calls, [])
    def test_error_contract_and_internal_exceptions_hidden(self):
        for result, status, code in (
            (WorkflowReadError("RESOURCE_NOT_FOUND"), 404, "RESOURCE_NOT_FOUND"),
            (WorkflowReadError("AUTH_ACCESS_DENIED"), 401, "AUTH_SESSION_EXPIRED"),
            (WorkflowReadError("LICENSE_OPERATION_DENIED"), 403, "LICENSE_OPERATION_DENIED"),
            (RuntimeError("private locator and traceback"), 503, "SYSTEM_UNAVAILABLE"),
            (None, 503, "SYSTEM_UNAVAILABLE"),
        ):
            self.result = result
            with self.subTest(code=code), TestClient(create_app(workflow_read_router=self.router), base_url="http://localhost") as client:
                response = client.get(self.path, headers=self.headers)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertNotIn("private locator", response.text)
                self.assertIn("trace_id", response.json())
    def test_invalid_session_and_default_app_do_not_mount(self):
        def expired(_token): raise SessionError("AUTH_SESSION_EXPIRED")
        self.sessions.validate = expired
        with TestClient(create_app(workflow_read_router=self.router), base_url="http://localhost") as client:
            self.assertEqual(client.get(self.path, headers=self.headers).status_code, 401)
        with TestClient(create_app(), base_url="http://localhost") as client:
            self.assertEqual(client.get(self.path, headers=self.headers).status_code, 404)
        self.assertEqual(self.calls, [])

    def test_foreign_project_projection_never_returned(self):
        self.result = replace(self.view, project_id=uuid.uuid4())
        with TestClient(create_app(workflow_read_router=self.router), base_url="http://localhost") as client:
            response = client.get(self.path, headers=self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(str(self.view.workflow_id), response.text)
