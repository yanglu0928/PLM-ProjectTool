from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.project.api.read_projects import create_project_read_router
from plm_assistant.modules.project.application.read_projects import (
    ProjectPage, ProjectReadError, ProjectView,
)


class Sessions:
    def __init__(self) -> None:
        self.fail = False

    def validate(self, token):
        if self.fail or token != b"a" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Projects:
    def __init__(self) -> None:
        self.view = ProjectView(
            uuid.uuid4(), "P1", "Synthetic project", "ACTIVE",
            datetime(2026, 9, 25, tzinfo=timezone.utc), '"v2"',
        )
        self.fail: str | None = None

    def list(self, query):
        if self.fail:
            raise ProjectReadError(self.fail)
        return ProjectPage((self.view,))

    def get(self, query, project_id):
        if self.fail:
            raise ProjectReadError(self.fail)
        if project_id != self.view.project_id:
            raise ProjectReadError("RESOURCE_NOT_FOUND")
        return self.view


class ProjectReadApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.projects = Sessions(), Projects()
        router = create_project_read_router(
            sessions=self.sessions, projects=self.projects,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"a" * 32).hex()}

    def test_default_closed_and_success_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get("/api/v1/projects").status_code, 404)
        response = self.client.get("/api/v1/projects", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["items"][0]["code"], "P1")
        self.assertEqual(response.json()["data"]["next_cursor"], None)
        self.assertEqual(response.headers["cache-control"], "no-store")
        detail = self.client.get(
            "/api/v1/projects/" + str(self.projects.view.project_id),
            headers=self.headers,
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.headers["etag"], '"v2"')
        self.assertEqual(detail.json()["data"]["created_at"], "2026-09-25T00:00:00Z")

    def test_query_and_cross_project_fail_closed(self) -> None:
        for suffix in ("?cursor=bad", "?page_size=0", "?page_size=201",
                       "?page_size=1&page_size=2"):
            with self.subTest(suffix=suffix):
                self.assertIn(self.client.get(
                    "/api/v1/projects" + suffix, headers=self.headers,
                ).status_code, (400, 422))
        response = self.client.get(
            "/api/v1/projects/" + str(uuid.uuid4()), headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_session_license_and_backend_failure(self) -> None:
        self.sessions.fail = True
        self.assertEqual(self.client.get(
            "/api/v1/projects", headers=self.headers,
        ).status_code, 401)
        self.sessions.fail = False
        for code, expected in (("LICENSE_OPERATION_DENIED", 403),
                               ("PROJECT_UNAVAILABLE", 503)):
            self.projects.fail = code
            with self.subTest(code=code):
                response = self.client.get("/api/v1/projects", headers=self.headers)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
