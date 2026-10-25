from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.create_project import create_project_create_router
from plm_assistant.modules.project.application.create_project import (
    CreatedProjectView, ProjectCreateError,
)


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Projects:
    def __init__(self) -> None:
        self.calls = 0
        self.fail: str | None = None
        self.view = CreatedProjectView(
            uuid.uuid4(), "P1", "Synthetic", "ACTIVE",
            datetime(2026, 9, 25, tzinfo=timezone.utc), '"v0"',
        )

    def create_idempotent(self, command, *, idempotency_key):
        self.calls += 1
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectCreateError(self.fail)
        assert command.code == "P1" and command.name == "Synthetic"
        assert idempotency_key == "a" * 16
        return self.view


class ProjectCreateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.projects = Projects()
        router = create_project_create_router(
            sessions=Sessions(), projects=self.projects,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "a" * 16,
        }
        self.body = {
            "code": "P1", "name": "Synthetic",
            "initial_manager_user_id": str(uuid.uuid4()),
        }

    def test_default_closed_and_created_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post("/api/v1/projects").status_code, 404)
        response = self.client.post("/api/v1/projects", headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.headers["location"],
                         "/api/v1/projects/" + str(self.projects.view.project_id))
        self.assertEqual(response.json()["data"]["created_at"], "2026-09-25T00:00:00Z")
        self.assertNotIn("project_member_id", response.text)

    def test_origin_session_csrf_and_key_gate(self) -> None:
        missing_origin = {key: value for key, value in self.headers.items() if key != "origin"}
        self.assertEqual(self.client.post(
            "/api/v1/projects", headers=missing_origin, json=self.body,
        ).status_code, 403)
        missing_csrf = {key: value for key, value in self.headers.items() if key != "x-csrf-token"}
        self.assertEqual(self.client.post(
            "/api/v1/projects", headers=missing_csrf, json=self.body,
        ).status_code, 403)
        missing_key = {key: value for key, value in self.headers.items() if key != "idempotency-key"}
        self.assertEqual(self.client.post(
            "/api/v1/projects", headers=missing_key, json=self.body,
        ).status_code, 422)
        self.assertEqual(self.projects.calls, 0)

    def test_malformed_and_oversized_json_rejected(self) -> None:
        for content in (
            b'{"code":"P1","code":"P2","name":"Synthetic","initial_manager_user_id":"a"}',
            b'{"code":NaN}',
            b"{" + b" " * 8192 + b"}",
        ):
            with self.subTest(content=content[:20]):
                response = self.client.post("/api/v1/projects", headers={
                    **self.headers, "content-type": "application/json",
                }, content=content)
                self.assertEqual(response.status_code, 400)
        wrong = {**self.body, "initial_manager_user_id": self.body["initial_manager_user_id"].upper()}
        self.assertEqual(self.client.post(
            "/api/v1/projects", headers=self.headers, json=wrong,
        ).status_code, 422)
        self.assertEqual(self.projects.calls, 0)

    def test_project_and_license_failures_are_safe(self) -> None:
        for code, expected in (("LICENSE", 403), ("AUTH_ACCESS_DENIED", 404),
                               ("CONFLICT_IDEMPOTENCY", 409),
                               ("PROJECT_USER_ALREADY_ASSIGNED", 409),
                               ("PROJECT_MANAGER_INVALID", 422)):
            self.projects.fail = code
            with self.subTest(code=code):
                response = self.client.post("/api/v1/projects", headers=self.headers,
                                            json=self.body)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
