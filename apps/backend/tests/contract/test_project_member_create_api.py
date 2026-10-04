from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.create_member import create_project_member_create_router
from plm_assistant.modules.project.application.create_member import ProjectMemberCreateError
from plm_assistant.modules.project.application.read_members import ProjectMemberView


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Members:
    def __init__(self):
        self.calls = 0
        self.fail = None
        self.user_id, self.department_id = uuid.uuid4(), uuid.uuid4()
        self.view = ProjectMemberView(
            uuid.uuid4(), self.user_id, "Synthetic User", "IMPLEMENTATION_MEMBER",
            self.department_id, "研发部", "ACTIVE",
            datetime(2026, 9, 25, tzinfo=timezone.utc), None, '"v0"',
        )

    def create_idempotent(self, command, *, idempotency_key):
        self.calls += 1
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectMemberCreateError(self.fail)
        assert command.user_id == self.user_id
        assert command.department_id == self.department_id
        assert command.role == "IMPLEMENTATION_MEMBER"
        assert idempotency_key == "a" * 16
        return self.view


class ProjectMemberCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.members = Members()
        self.project_id = uuid.uuid4()
        router = create_project_member_create_router(
            sessions=Sessions(), members=self.members,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_member_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project_id}/members"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "a" * 16,
        }
        self.body = {
            "user_id": str(self.members.user_id),
            "role": "IMPLEMENTATION_MEMBER",
            "department_id": str(self.members.department_id),
        }

    def test_default_closed_and_safe_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.headers["location"], self.path + "/" + str(self.members.view.member_id))
        self.assertEqual(response.json()["data"]["user"]["display_name"], "Synthetic User")
        self.assertEqual(response.json()["data"]["effective_at"], "2026-09-25T00:00:00Z")
        self.assertNotIn("project_id", response.json()["data"])

    def test_security_headers_and_body_rejected_before_service(self):
        for dropped, status in (("origin", 403), ("x-csrf-token", 403),
                                ("idempotency-key", 422), ("cookie", 401)):
            with self.subTest(dropped=dropped):
                headers = {k: v for k, v in self.headers.items() if k != dropped}
                self.assertEqual(self.client.post(self.path, headers=headers,
                                                  json=self.body).status_code, status)
        for body, status in (({**self.body, "project_id": str(self.project_id)}, 400),
                             ({**self.body, "user_id": str(self.members.user_id).upper()}, 422),
                             ({**self.body, "effective_at": "2026-09-25T00:00:00"}, 422)):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.path, headers=self.headers,
                                                  json=body).status_code, status)
        response = self.client.post(self.path, headers={
            **self.headers, "content-type": "application/json",
        }, content=b'{"role":"A","role":"B"}')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.members.calls, 0)

    def test_permission_license_and_conflicts_are_safe(self):
        for code, status in (("LICENSE", 403), ("RESOURCE_NOT_FOUND", 404),
                             ("PROJECT_ARCHIVED", 409),
                             ("PROJECT_USER_ALREADY_ASSIGNED", 409),
                             ("PROJECT_ROLE_INVALID", 422),
                             ("CONFLICT_IDEMPOTENCY", 409)):
            self.members.fail = code
            with self.subTest(code=code):
                response = self.client.post(self.path, headers=self.headers, json=self.body)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
