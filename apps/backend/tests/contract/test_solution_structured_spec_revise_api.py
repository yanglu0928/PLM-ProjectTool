"""Frozen SOL_SPEC_REVISE default-closed HTTP contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.structured_spec_revise import (
    create_structured_spec_revise_router,
)
from plm_assistant.modules.solution.application.revise_structured_spec import (
    StructuredSpecReviseError,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecInitialView,
)


PROJECT, REQUIREMENT, REQ_VERSION, SECTION, SECTION_VERSION = (
    uuid.uuid4() for _ in range(5))
EVIDENCE, PREDECESSOR, VERSION, SERIES, ACTOR = (
    uuid.uuid4() for _ in range(5))


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Revises:
    def __init__(self):
        self.commands = []
        self.error = None
        self.project = PROJECT
        self.predecessor = PREDECESSOR
        self.version_no = 2

    def revise(self, command):
        self.commands.append(command)
        if self.error:
            raise StructuredSpecReviseError(self.error)
        draft = validate_structured_spec_draft(command.draft)
        return StructuredSpecInitialView(
            VERSION, SERIES, self.project, draft.spec_type, self.version_no,
            b"f" * 32, draft.payload_json, draft.payload_fingerprint,
            draft.requirement_refs, draft.section_refs, draft.evidence_ids,
            self.predecessor, ACTOR,
            datetime(2026, 10, 16, tzinfo=timezone.utc))


class StructuredSpecReviseApiTests(unittest.TestCase):
    def setUp(self):
        self.revises = Revises()
        self.path = (
            f"/api/v1/projects/{PROJECT}/structured-solution-specs/"
            f"{PREDECESSOR}:revise")
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "r" * 16,
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
            solution_structured_spec_revise_router=create_structured_spec_revise_router(
                sessions=Sessions(),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                revises=self.revises)), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_replacement_draft(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.path, headers=self.headers, json=self.body).status_code)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(201, response.status_code)
        expected = f"/api/v1/projects/{PROJECT}/structured-solution-specs/{VERSION}"
        self.assertEqual(response.headers["location"], expected)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("etag", response.headers)
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual((data["structured_solution_spec_id"], data["spec_series_id"]),
                         (str(VERSION), str(SERIES)))
        self.assertEqual((data["version_no"], data["version_state"]), (2, "DRAFT"))
        self.assertEqual(data["supersedes_version_ref"], str(PREDECESSOR))
        self.assertEqual(data["payload"], self.body["payload"])
        command = self.revises.commands[0]
        self.assertEqual((command.project_id, command.spec_id),
                         (PROJECT, PREDECESSOR))
        self.assertIsNone(command.draft.spec_series_id)
        self.assertIsNone(command.draft.supersedes_version_ref)

    def test_auth_strict_body_query_and_path(self):
        cases = (
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"},
             self.body, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, self.body, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()},
             self.body, 403),
            (self.path, {k: v for k, v in self.headers.items()
                         if k != "idempotency-key"}, self.body, 422),
            (self.path + "?force=true", self.headers, self.body, 400),
            (self.path, self.headers, {**self.body, "spec_series_id": str(SERIES)}, 400),
            (self.path, self.headers,
             {**self.body, "artifact_ids": [str(uuid.uuid4())]}, 422),
            (self.path, self.headers, {**self.body, "requirement_refs": []}, 422),
            (self.path.replace(str(PREDECESSOR), "invalid"),
             self.headers, self.body, 422),
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
            ("VERSION_CONFLICT", 409), ("CONFLICT_STATE", 409),
            ("CONFLICT_IDEMPOTENCY", 409), ("SOURCE_UNAVAILABLE", 503),
            ("SOLUTION_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.revises.error = code
                response = self.client.post(
                    self.path, headers=self.headers, json=self.body)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("Traceback", response.text)

    def test_wrong_result_binding_fails_closed(self):
        for attribute, value in (
            ("project", uuid.uuid4()),
            ("predecessor", uuid.uuid4()),
            ("version_no", 1),
        ):
            with self.subTest(attribute=attribute):
                setattr(self.revises, attribute, value)
                self.assertEqual(503, self.client.post(
                    self.path, headers=self.headers, json=self.body).status_code)
                setattr(self.revises, attribute, {
                    "project": PROJECT,
                    "predecessor": PREDECESSOR,
                    "version_no": 2,
                }[attribute])


if __name__ == "__main__":
    unittest.main()
