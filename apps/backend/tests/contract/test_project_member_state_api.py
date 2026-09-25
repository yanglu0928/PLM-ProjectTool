from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.change_member_state import create_project_member_state_router
from plm_assistant.modules.project.application.change_member_state import ProjectMemberStateError
from plm_assistant.modules.project.application.read_members import ProjectMemberView


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Members:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.project_id, self.member_id = uuid.uuid4(), uuid.uuid4()
        self.user_id, self.department_id = uuid.uuid4(), uuid.uuid4()

    def _execute(self, command, key, state):
        self.calls.append(state)
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectMemberStateError(self.fail)
        assert command.project_id == self.project_id
        assert command.member_id == self.member_id
        assert command.expected_version == 0
        assert key == "a" * 16
        return ProjectMemberView(
            self.member_id, self.user_id, "Synthetic User", "CUSTOMER_MEMBER",
            self.department_id, "研发部", state,
            datetime(2026, 9, 25, tzinfo=timezone.utc),
            datetime(2026, 9, 26, tzinfo=timezone.utc) if state == "REMOVED" else None,
            '"v1"',
        )

    def suspend_idempotent(self, command, *, idempotency_key):
        return self._execute(command, idempotency_key, "SUSPENDED")

    def resume_idempotent(self, command, *, idempotency_key):
        return self._execute(command, idempotency_key, "ACTIVE")

    def remove_idempotent(self, command, *, idempotency_key):
        return self._execute(command, idempotency_key, "REMOVED")


class ProjectMemberStateApiTests(unittest.TestCase):
    def setUp(self):
        self.members = Members()
        router = create_project_member_state_router(
            sessions=Sessions(), members=self.members,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_member_state_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.base = (f"/api/v1/projects/{self.members.project_id}"
                     f"/members/{self.members.member_id}")
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "if-match": '"v0"', "idempotency-key": "a" * 16,
        }

    def test_default_closed_and_three_safe_responses(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(bare.post(self.base + ":" + action).status_code, 404)
        for action, state in (("suspend", "SUSPENDED"),
                              ("resume", "ACTIVE"), ("remove", "REMOVED")):
            with self.subTest(action=action):
                response = self.client.post(self.base + ":" + action,
                                            headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["etag"], '"v1"')
                self.assertEqual(response.json()["data"]["state"], state)
                self.assertNotIn("project_id", response.json()["data"])
        self.assertEqual(self.members.calls, ["SUSPENDED", "ACTIVE", "REMOVED"])

    def test_security_and_body_preconditions(self):
        path = self.base + ":suspend"
        for dropped, status in (("origin", 403), ("cookie", 401),
                                ("x-csrf-token", 403), ("if-match", 428),
                                ("idempotency-key", 422)):
            with self.subTest(dropped=dropped):
                headers = {k: v for k, v in self.headers.items() if k != dropped}
                self.assertEqual(self.client.post(path, headers=headers).status_code, status)
        self.assertEqual(self.client.post(path, headers=self.headers,
                                          json={}).status_code, 400)
        self.assertEqual(self.client.post(path, headers={
            **self.headers, "if-match": 'W/"v0"',
        }).status_code, 400)
        self.assertEqual(self.members.calls, [])

    def test_service_errors_are_safe(self):
        for code, status in (("LICENSE", 403), ("AUTH_ACCESS_DENIED", 401),
                             ("RESOURCE_NOT_FOUND", 404), ("PROJECT_ARCHIVED", 409),
                             ("PROJECT_ROLE_INVALID", 422), ("CONFLICT_STATE", 409),
                             ("CONFLICT_VERSION", 409), ("CONFLICT_IDEMPOTENCY", 409)):
            self.members.fail = code
            with self.subTest(code=code):
                response = self.client.post(self.base + ":remove", headers=self.headers)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
