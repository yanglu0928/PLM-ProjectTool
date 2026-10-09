"""Frozen SectionVersion CREATE opt-in HTTP contract and closed defaults."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.section_version_create import (
    create_section_version_create_router,
)
from plm_assistant.modules.solution.application.create_section_version import (
    SectionVersionCreateError, SectionVersionInitialView,
)


PROJECT, SECTION, DOCUMENT, REQUIREMENT, REQUIREMENT_VERSION = (
    uuid.uuid4() for _ in range(5))
EVIDENCE, VERSION, ACTOR = (uuid.uuid4() for _ in range(3))


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
            raise SectionVersionCreateError(self.error)
        draft = command.draft
        return SectionVersionInitialView(
            VERSION, draft.solution_section_id, self.project, 1,
            draft.title, draft.content_document_version_ref, b"f" * 32,
            draft.requirement_refs, draft.evidence_ids,
            draft.assumptions, draft.exclusions,
            None, ACTOR, datetime(2026, 10, 9, tzinfo=timezone.utc))


class SectionVersionCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.creates = Creates()
        self.path = f"/api/v1/projects/{PROJECT}/solution-sections/{SECTION}/versions"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "v" * 16,
        }
        self.body = {
            "title": "Implementation body",
            "content_document_version_ref": str(DOCUMENT),
            "content_artifact_ref": None,
            "requirement_refs": [{
                "requirement_id": str(REQUIREMENT),
                "requirement_version_id": str(REQUIREMENT_VERSION)}],
            "evidence_ids": [str(EVIDENCE)],
            "assumptions": [{"note": "synthetic"}], "exclusions": [],
        }
        self.client = TestClient(create_app(
            solution_section_version_create_router=create_section_version_create_router(
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
        self.assertEqual((data["solution_section_version_id"], data["version_state"]),
                         (str(VERSION), "DRAFT"))
        self.assertEqual(data["content_document_version_ref"], str(DOCUMENT))
        self.assertIsNone(data["content_artifact_ref"])
        self.assertEqual(data["requirement_refs"], self.body["requirement_refs"])
        self.assertEqual(data["evidence_ids"], self.body["evidence_ids"])
        self.assertEqual((data["declared_requirement_count"],
                          data["declared_evidence_count"]), (1, 1))
        self.assertEqual(data["created_at"], "2026-10-09T00:00:00Z")

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
            (self.path, self.headers, {**self.body, "requirement_refs": "bad"}, 422),
            (self.path, self.headers, {**self.body, "content_artifact_ref": str(uuid.uuid4())}, 422),
            (self.path, self.headers, {**self.body, "evidence_ids": ["bad"]}, 422),
            (self.path.replace(str(SECTION), "invalid"), self.headers, self.body, 422),
        )
        for path, headers, body, expected in cases:
            with self.subTest(path=path, expected=expected):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())

    def test_duplicate_json_nonstandard_and_error_projection(self):
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"title":"a","title":"b"}').status_code)
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"title":NaN}').status_code)
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
