"""Frozen OutlineVersion CREATE opt-in HTTP contract and closed defaults."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.outline_version_create import (
    create_outline_version_create_router,
)
from plm_assistant.modules.solution.application.create_outline_version import (
    OutlineVersionCreateError, OutlineVersionInitialView,
)


PROJECT, OUTLINE, SECTION, REQUIREMENT, REQUIREMENT_VERSION = (
    uuid.uuid4() for _ in range(5))
REFERENCE, REFERENCE_VERSION, VERSION, ACTOR = (uuid.uuid4() for _ in range(4))


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
        self.project = PROJECT

    def create(self, command):
        self.commands.append(command)
        if self.error:
            raise OutlineVersionCreateError(self.error)
        return OutlineVersionInitialView(
            VERSION, command.draft.solution_outline_id, self.project,
            1, b"f" * 32, command.draft.missing_declarations,
            command.draft.conflict_declarations,
            len(command.draft.section_ids), len(command.draft.requirement_refs),
            len(command.draft.reference_refs), None, ACTOR,
            datetime(2026, 10, 9, tzinfo=timezone.utc))


class OutlineVersionCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.creates = Creates()
        self.path = f"/api/v1/projects/{PROJECT}/solution-outlines/{OUTLINE}/versions"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "v" * 16,
        }
        self.body = {
            "section_ids": [str(SECTION)],
            "requirement_refs": [{
                "requirement_id": str(REQUIREMENT),
                "requirement_version_id": str(REQUIREMENT_VERSION)}],
            "reference_refs": [{
                "scope": "GLOBAL", "reference_solution_id": str(REFERENCE),
                "reference_version_id": str(REFERENCE_VERSION)}],
            "missing_declarations": [], "conflict_declarations": [],
        }
        self.client = TestClient(create_app(
            solution_outline_version_create_router=create_outline_version_create_router(
                sessions=Sessions(),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                creates=self.creates)),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_first_draft_response(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.path, headers=self.headers, json=self.body).status_code)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(201, response.status_code)
        self.assertEqual(f"{self.path}/{VERSION}", response.headers["location"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertNotIn("etag", response.headers)
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual((data["solution_outline_version_id"], data["version_state"]),
                         (str(VERSION), "DRAFT"))
        self.assertEqual(data["content_fingerprint"], (b"f" * 32).hex())
        self.assertEqual((data["declared_section_count"],
                          data["declared_requirement_count"],
                          data["declared_reference_count"]), (1, 1, 1))
        self.assertEqual(data["created_at"], "2026-10-09T00:00:00Z")
        self.assertEqual(self.creates.commands[-1].draft.reference_refs[0].scope,
                         "GLOBAL")
        self.assertEqual(self.creates.commands[-1].session_token, b"s" * 32)

    def test_auth_strict_body_and_path(self):
        cases = (
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"},
             self.body, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"},
             self.body, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()},
             self.body, 403),
            (self.path, {k: v for k, v in self.headers.items()
                         if k != "idempotency-key"}, self.body, 422),
            (self.path + "?scope=GLOBAL", self.headers, self.body, 400),
            (self.path, self.headers, {**self.body, "project_id": str(PROJECT)}, 400),
            (self.path, self.headers, {**self.body, "section_ids": "bad"}, 422),
            (self.path, self.headers, {**self.body, "reference_refs": [{
                **self.body["reference_refs"][0], "scope": "OTHER"}]}, 422),
            (self.path, self.headers, {**self.body, "requirement_refs": [{
                **self.body["requirement_refs"][0], "extra": 1}]}, 422),
            (self.path.replace(str(OUTLINE), "invalid"), self.headers, self.body, 422),
        )
        for path, headers, body, expected in cases:
            with self.subTest(path=path, expected=expected):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())
        self.assertEqual(self.creates.commands, [])

    def test_duplicate_json_nonstandard_and_error_projection(self):
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"section_ids":[],"section_ids":[]}').status_code)
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"section_ids":NaN}').status_code)
        for code, expected in (
            ("RESOURCE_NOT_FOUND", 404), ("AUTH_ACCESS_DENIED", 404),
            ("PROJECT_ARCHIVED", 409), ("LICENSE_OPERATION_DENIED", 403),
            ("CONFLICT_IDEMPOTENCY", 409), ("SOURCE_UNAVAILABLE", 503),
            ("SOLUTION_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.creates.error = code
                response = self.client.post(
                    self.path, headers=self.headers, json=self.body)
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)

    def test_wrong_project_result_fails_closed(self):
        self.creates.project = uuid.uuid4()
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)


if __name__ == "__main__":
    unittest.main()
