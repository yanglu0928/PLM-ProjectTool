from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.patch_member import create_project_member_patch_router
from plm_assistant.modules.project.application.patch_member import ProjectMemberPatchError
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
        self.project_id, self.member_id = uuid.uuid4(), uuid.uuid4()
        self.view = ProjectMemberView(
            self.member_id, uuid.uuid4(), "Synthetic User", "CUSTOMER_MEMBER",
            uuid.uuid4(), "研发部", "ACTIVE",
            datetime(2026, 9, 25, tzinfo=timezone.utc), None, '"v1"',
        )

    def patch(self, command):
        self.calls += 1
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectMemberPatchError(self.fail)
        assert command.project_id == self.project_id
        assert command.member_id == self.member_id
        assert command.expected_version == 0
        assert command.role == "CUSTOMER_MEMBER"
        return self.view


class ProjectMemberPatchApiTests(unittest.TestCase):
    def setUp(self):
        self.members = Members()
        router = create_project_member_patch_router(
            sessions=Sessions(), members=self.members,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_member_patch_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.members.project_id}"
                     f"/members/{self.members.member_id}")
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "if-match": '"v0"',
        }

    def test_default_closed_and_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.patch(self.path).status_code, 404)
        response = self.client.patch(self.path, headers=self.headers,
                                     json={"role": "CUSTOMER_MEMBER"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.json()["data"]["role"], "CUSTOMER_MEMBER")
        self.assertEqual(response.json()["data"]["department"]["name"], "研发部")
        self.assertEqual(response.json()["data"]["effective_at"], "2026-09-25T00:00:00Z")
        self.assertNotIn("project_id", response.json()["data"])

    def test_security_preconditions_and_input_rejected_before_service(self):
        for dropped, status in (("origin", 403), ("cookie", 401),
                                ("x-csrf-token", 403), ("if-match", 428)):
            with self.subTest(dropped=dropped):
                headers = {k: v for k, v in self.headers.items() if k != dropped}
                self.assertEqual(self.client.patch(self.path, headers=headers,
                                                   json={"role": "CUSTOMER_MEMBER"}).status_code, status)
        for etag in ('W/"v0"', '"v01"', '*'):
            with self.subTest(etag=etag):
                self.assertEqual(self.client.patch(self.path, headers={
                    **self.headers, "if-match": etag,
                }, json={"role": "CUSTOMER_MEMBER"}).status_code, 400)
        for body, status in (({}, 400), ({"role": "CUSTOMER_MEMBER", "user_id": str(uuid.uuid4())}, 400),
                             ({"role": None}, 422), ({"department_id": str(uuid.uuid4()).upper()}, 422)):
            with self.subTest(body=body):
                self.assertEqual(self.client.patch(self.path, headers=self.headers,
                                                   json=body).status_code, status)
        self.assertEqual(self.members.calls, 0)

    def test_service_error_mapping(self):
        for code, status in (("LICENSE", 403), ("AUTH_ACCESS_DENIED", 401),
                             ("RESOURCE_NOT_FOUND", 404), ("PROJECT_ARCHIVED", 409),
                             ("PROJECT_ROLE_INVALID", 422), ("CONFLICT_VERSION", 409)):
            self.members.fail = code
            with self.subTest(code=code):
                response = self.client.patch(self.path, headers=self.headers,
                                             json={"role": "CUSTOMER_MEMBER"})
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
