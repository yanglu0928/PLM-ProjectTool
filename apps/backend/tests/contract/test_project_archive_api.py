from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.archive_project import create_project_archive_router
from plm_assistant.modules.project.application.read_projects import ProjectView
from plm_assistant.modules.project.application.write_project import ProjectWriteError


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"m" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Writes:
    def __init__(self, project_id):
        self.project_id = project_id
        self.calls = 0
        self.fail = None

    def archive_idempotent(self, command, *, idempotency_key):
        self.calls += 1
        assert command.project_id == self.project_id
        assert command.expected_version == 0
        assert idempotency_key == "archive-key-123456"
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectWriteError(self.fail)
        return ProjectView(
            self.project_id, "P1", "Name", "ARCHIVED",
            datetime(2026, 9, 25, tzinfo=timezone.utc), '"v1"',
        )


class ProjectArchiveApiTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.writes = Writes(self.project_id)
        router = create_project_archive_router(
            sessions=Sessions(), writes=self.writes,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_archive_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project_id}:archive"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"m" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "if-match": '"v0"',
            "idempotency-key": "archive-key-123456",
        }

    def test_default_closed_and_archived_success(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.json()["data"]["state"], "ARCHIVED")
        self.assertEqual(self.writes.calls, 1)

    def test_missing_headers_body_and_origin_rejected(self):
        for missing, expected in (("idempotency-key", 422), ("if-match", 428),
                                  ("x-csrf-token", 403), ("cookie", 401)):
            headers = {k: v for k, v in self.headers.items() if k != missing}
            with self.subTest(missing=missing):
                self.assertEqual(self.client.post(self.path, headers=headers).status_code, expected)
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                         content=b"{}").status_code, 400)
        self.assertEqual(self.client.post(self.path, headers={
            **self.headers, "origin": "https://evil.example.test",
        }).status_code, 403)
        self.assertEqual(self.writes.calls, 0)

    def test_permission_conflict_and_license_are_safe(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("CONFLICT_IDEMPOTENCY", 409),
                               ("PROJECT_ARCHIVED", 409), ("LICENSE", 403)):
            self.writes.fail = code
            with self.subTest(code=code):
                response = self.client.post(self.path, headers=self.headers)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
