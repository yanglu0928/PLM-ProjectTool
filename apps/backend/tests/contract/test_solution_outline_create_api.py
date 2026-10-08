"""Frozen SOL_OUTLINE_CREATE opt-in HTTP shape and closed defaults."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.outline_create import create_outline_create_router
from plm_assistant.modules.solution.application.create_outline import (
    OutlineCreateError, OutlineInitialView,
)


PROJECT, OUTLINE = uuid.uuid4(), uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Creates:
    def __init__(self):
        self.commands = []
        self.error = None
        self.result_project = PROJECT

    def create(self, command):
        self.commands.append(command)
        if self.error:
            raise OutlineCreateError(self.error)
        return OutlineInitialView(
            OUTLINE, self.result_project, command.name,
            datetime(2026, 10, 9, tzinfo=timezone.utc),
        )


class SolutionOutlineCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.creates = Creates()
        self.path = f"/api/v1/projects/{PROJECT}/solution-outlines"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "o" * 16,
        }
        router = create_outline_create_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            creates=self.creates,
        )
        self.client = TestClient(
            create_app(solution_outline_create_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)

    def test_default_closed_and_created_contract(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.path, headers=self.headers, json={"name": "Implementation"}).status_code)
        response = self.client.post(
            self.path, headers=self.headers, json={"name": "Implementation"})
        self.assertEqual(201, response.status_code)
        self.assertEqual('"v0"', response.headers["etag"])
        self.assertEqual(f"{self.path}/{OUTLINE}", response.headers["location"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "solution_outline_id": str(OUTLINE), "project_id": str(PROJECT),
            "name": "Implementation", "outline_state": "ACTIVE",
            "current_approved_version_ref": None,
            "created_at": "2026-10-09T00:00:00Z", "etag": '"v0"',
        }, response.json()["data"])
        self.assertEqual(PROJECT, self.creates.commands[-1].project_id)
        self.assertEqual(b"s" * 32, self.creates.commands[-1].session_token)
        self.assertEqual(b"c" * 32, self.creates.commands[-1].csrf_token)

    def test_auth_scope_and_strict_body(self):
        cases = (
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"},
             {"name": "A"}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"},
             {"name": "A"}, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()},
             {"name": "A"}, 403),
            (self.path, {k: v for k, v in self.headers.items() if k != "idempotency-key"},
             {"name": "A"}, 422),
            (self.path + "?scope=GLOBAL", self.headers, {"name": "A"}, 400),
            (self.path, self.headers, {"name": "A", "project_id": str(PROJECT)}, 400),
            (self.path, self.headers, {"name": []}, 422),
        )
        for path, headers, body, expected in cases:
            with self.subTest(expected=expected, path=path, body=body):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())
        self.assertFalse(self.creates.commands)
        self.assertEqual(404, self.client.post(
            "/api/v1/global/solution-outlines", headers=self.headers,
            json={"name": "A"}).status_code)

    def test_duplicate_json_and_error_projection(self):
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"name":"A","name":"B"}').status_code)
        for code, expected in (
            ("RESOURCE_NOT_FOUND", 404), ("AUTH_ACCESS_DENIED", 404),
            ("PROJECT_ARCHIVED", 409), ("LICENSE_OPERATION_DENIED", 403),
            ("CONFLICT_IDEMPOTENCY", 409), ("SOLUTION_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.creates.error = code
                response = self.client.post(
                    self.path, headers=self.headers, json={"name": "A"})
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)

    def test_wrong_project_result_fails_closed(self):
        self.creates.result_project = uuid.uuid4()
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json={"name": "A"}).status_code)


if __name__ == "__main__":
    unittest.main()
