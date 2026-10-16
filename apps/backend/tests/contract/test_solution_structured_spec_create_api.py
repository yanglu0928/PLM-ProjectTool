"""Frozen SOL_SPEC_CREATE default-closed HTTP contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.structured_spec_create import (
    create_structured_spec_create_router,
)
from plm_assistant.modules.solution.application.create_structured_spec import (
    StructuredSpecCreateError,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecInitialView,
)


PROJECT, REQUIREMENT, REQ_VERSION, SECTION, SECTION_VERSION = (
    uuid.uuid4() for _ in range(5))
EVIDENCE, VERSION, SERIES, ACTOR = (uuid.uuid4() for _ in range(4))


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
            raise StructuredSpecCreateError(self.error)
        draft = validate_structured_spec_draft(command.draft)
        return StructuredSpecInitialView(
            VERSION, SERIES, self.project, draft.spec_type, 1,
            b"f" * 32, draft.payload_json, draft.payload_fingerprint,
            draft.requirement_refs, draft.section_refs, draft.evidence_ids,
            None, ACTOR, datetime(2026, 10, 12, tzinfo=timezone.utc))


class StructuredSpecCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.creates = Creates()
        self.path = f"/api/v1/projects/{PROJECT}/structured-solution-specs"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "s" * 16,
        }
        self.body = {
            "spec_type": "MIGRATION_SPEC", "payload": {
                "assumptions": ["synthetic pending confirmation"],
                "exclusions": [], "source_system": "old", "target_system": "new",
                "scope": "parts", "cleansing_rules": ["deduplicate"],
                "field_mappings": [{"source": "old_id", "target": "part_id"}],
                "trial_plan": "trial", "reconciliation_plan": "reconcile",
                "rollback_plan": "snapshot", "acceptance_criteria": "zero difference",
            },
            "requirement_refs": [{"requirement_id": str(REQUIREMENT),
                                  "requirement_version_id": str(REQ_VERSION)}],
            "section_refs": [{"solution_section_id": str(SECTION),
                              "solution_section_version_id": str(SECTION_VERSION)}],
            "evidence_ids": [str(EVIDENCE)], "artifact_ids": [],
        }
        self.client = TestClient(create_app(
            solution_structured_spec_create_router=create_structured_spec_create_router(
                sessions=Sessions(),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                creates=self.creates)), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_first_draft(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.path, headers=self.headers, json=self.body).status_code)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(201, response.status_code)
        self.assertEqual(response.headers["location"], f"{self.path}/{VERSION}")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("etag", response.headers)
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual((data["structured_solution_spec_id"], data["spec_series_id"]),
                         (str(VERSION), str(SERIES)))
        self.assertEqual((data["version_no"], data["version_state"]), (1, "DRAFT"))
        self.assertEqual(data["payload"], self.body["payload"])
        self.assertEqual(data["requirement_refs"], self.body["requirement_refs"])
        self.assertEqual(data["section_refs"], self.body["section_refs"])
        self.assertEqual(data["evidence_ids"], self.body["evidence_ids"])
        self.assertEqual(data["artifact_ids"], [])
        self.assertEqual(data["created_at"], "2026-10-12T00:00:00Z")

    def test_auth_strict_body_and_path(self):
        cases = (
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"},
             self.body, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, self.body, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()},
             self.body, 403),
            (self.path, {k: v for k, v in self.headers.items()
                         if k != "idempotency-key"}, self.body, 422),
            (self.path + "?scope=GLOBAL", self.headers, self.body, 400),
            (self.path, self.headers, {**self.body, "project_id": str(PROJECT)}, 400),
            (self.path, self.headers, {**self.body, "artifact_ids": [str(uuid.uuid4())]}, 422),
            (self.path, self.headers, {**self.body, "section_refs": []}, 422),
            (self.path, self.headers, {**self.body, "evidence_ids": ["bad"]}, 422),
            (self.path.replace(str(PROJECT), "invalid"), self.headers, self.body, 422),
        )
        for path, headers, body, expected in cases:
            with self.subTest(path=path, expected=expected):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(response.status_code, expected)
                self.assertIn("error", response.json())

    def test_duplicate_json_nonstandard_and_error_projection(self):
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"spec_type":"a","spec_type":"b"}').status_code)
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers, content='{"spec_type":NaN}').status_code)
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
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("Traceback", response.text)

    def test_wrong_project_result_fails_closed(self):
        self.creates.project = uuid.uuid4()
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)


if __name__ == "__main__":
    unittest.main()
