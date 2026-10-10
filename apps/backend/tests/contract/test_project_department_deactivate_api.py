from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.deactivate_department import create_project_department_deactivate_router
from plm_assistant.modules.project.application.deactivate_department import ProjectDepartmentDeactivateError
from plm_assistant.modules.project.application.read_departments import DepartmentView


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Departments:
    def __init__(self):
        self.calls = 0
        self.fail = None
        self.project_id, self.department_id = uuid.uuid4(), uuid.uuid4()
        self.view = DepartmentView(
            self.department_id, "RD", "研发部", "INACTIVE",
            datetime(2026, 9, 25, tzinfo=timezone.utc), '"v1"',
        )

    def deactivate_idempotent(self, command, *, idempotency_key):
        self.calls += 1
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectDepartmentDeactivateError(self.fail)
        assert command.project_id == self.project_id
        assert command.department_id == self.department_id
        assert command.expected_version == 0
        assert idempotency_key == "a" * 16
        return self.view


class ProjectDepartmentDeactivateApiTests(unittest.TestCase):
    def setUp(self):
        self.departments = Departments()
        router = create_project_department_deactivate_router(
            sessions=Sessions(), departments=self.departments,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_department_deactivate_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.departments.project_id}"
                     f"/departments/{self.departments.department_id}:deactivate")
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "if-match": '"v0"', "idempotency-key": "a" * 16,
        }

    def test_default_closed_and_safe_result(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"]["state"], "INACTIVE")
        self.assertNotIn("project_id", response.json()["data"])

    def test_preconditions_and_body_rejected_before_service(self):
        for dropped, status in (("origin", 403), ("cookie", 401),
                                ("x-csrf-token", 403), ("if-match", 428),
                                ("idempotency-key", 422)):
            with self.subTest(dropped=dropped):
                headers = {key: value for key, value in self.headers.items() if key != dropped}
                self.assertEqual(self.client.post(self.path, headers=headers).status_code, status)
        for etag in ('W/"v0"', '"v01"', '*'):
            with self.subTest(etag=etag):
                self.assertEqual(self.client.post(self.path, headers={**self.headers, "if-match": etag}).status_code, 400)
        self.assertEqual(self.client.post(self.path, headers=self.headers, json={}).status_code, 400)
        self.assertEqual(self.departments.calls, 0)

    def test_service_errors_are_safe(self):
        for code, status in (("LICENSE", 403), ("AUTH_ACCESS_DENIED", 401),
                             ("RESOURCE_NOT_FOUND", 404), ("PROJECT_ARCHIVED", 409),
                             ("PROJECT_DEPARTMENT_IN_USE", 409), ("CONFLICT_VERSION", 409),
                             ("CONFLICT_STATE", 409), ("CONFLICT_IDEMPOTENCY", 409)):
            self.departments.fail = code
            with self.subTest(code=code):
                response = self.client.post(self.path, headers=self.headers)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
