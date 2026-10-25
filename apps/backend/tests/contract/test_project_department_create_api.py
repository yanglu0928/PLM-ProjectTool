from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.create_department import create_project_department_create_router
from plm_assistant.modules.project.application.create_department import ProjectDepartmentCreateError
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
        self.view = DepartmentView(
            uuid.uuid4(), "ABC", "研发部", "ACTIVE",
            datetime(2026, 9, 25, tzinfo=timezone.utc), '"v0"',
        )

    def create_idempotent(self, command, *, idempotency_key):
        self.calls += 1
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectDepartmentCreateError(self.fail)
        assert command.code == "ABC"
        assert command.name == "研发部"
        assert idempotency_key == "a" * 16
        return self.view


class ProjectDepartmentCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.departments = Departments()
        self.project_id = uuid.uuid4()
        router = create_project_department_create_router(
            sessions=Sessions(), departments=self.departments,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_department_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project_id}/departments"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "a" * 16,
        }
        self.body = {"code": "ABC", "name": "研发部"}

    def test_default_closed_and_safe_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.headers["location"], self.path + "/" + str(self.departments.view.department_id))
        self.assertEqual(response.json()["data"]["created_at"], "2026-09-25T00:00:00Z")
        self.assertEqual(set(response.json()["data"]), {
            "department_id", "code", "name", "state", "created_at", "etag",
        })

    def test_security_headers_and_body_rejected_before_service(self):
        for dropped, status in (("origin", 403), ("x-csrf-token", 403),
                                ("idempotency-key", 422), ("cookie", 401)):
            with self.subTest(dropped=dropped):
                headers = {k: v for k, v in self.headers.items() if k != dropped}
                self.assertEqual(self.client.post(self.path, headers=headers,
                                                  json=self.body).status_code, status)
        for body, status in (({**self.body, "project_id": str(self.project_id)}, 400),
                             ({"code": "ABC"}, 400),
                             ({"code": None, "name": "研发部"}, 422)):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.path, headers=self.headers,
                                                  json=body).status_code, status)
        response = self.client.post(self.path, headers={
            **self.headers, "content-type": "application/json",
        }, content=b'{"code":"A","code":"B","name":"C"}')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.departments.calls, 0)

    def test_permission_license_and_conflicts_are_safe(self):
        for code, status in (("LICENSE", 403), ("RESOURCE_NOT_FOUND", 404),
                             ("PROJECT_ARCHIVED", 409), ("CONFLICT_DUPLICATE", 409),
                             ("CONFLICT_IDEMPOTENCY", 409)):
            self.departments.fail = code
            with self.subTest(code=code):
                response = self.client.post(self.path, headers=self.headers, json=self.body)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
