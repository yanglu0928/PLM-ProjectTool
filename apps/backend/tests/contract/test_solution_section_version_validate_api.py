"""Frozen SectionVersion VALIDATE opt-in HTTP projection contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.section_version_validate import (
    create_section_version_validate_router,
)
from plm_assistant.modules.solution.application.section_version_validation_contract import (
    SectionVersionValidationFacts, SectionVersionValidationSnapshot,
    build_section_version_validation_report,
)
from plm_assistant.modules.solution.application.validate_section_version import (
    SectionVersionValidationError,
)


PROJECT, SECTION, VERSION, AUDIT = (uuid.uuid4() for _ in range(4))
OBSERVED = datetime(2026, 10, 12, tzinfo=timezone.utc)


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Validations:
    def __init__(self):
        self.commands = []
        self.first_trace = None
        self.error = None
        self.project = PROJECT

    def validate(self, command):
        self.commands.append(command)
        if self.error:
            raise SectionVersionValidationError(self.error)
        if self.first_trace is None:
            self.first_trace = command.trace_id
        facts = SectionVersionValidationFacts(
            "PASS", "PASS", "PASS", "PASS", "UNAVAILABLE", "UNAVAILABLE")
        return build_section_version_validation_report(
            command.__class__(command.session_token, command.csrf_token,
                              self.first_trace, self.project,
                              command.solution_section_id,
                              command.solution_section_version_id,
                              command.idempotency_key),
            SectionVersionValidationSnapshot(
                self.project, command.solution_section_id,
                command.solution_section_version_id, 1, "DRAFT", b"f" * 32, 1, 1),
            facts, audit_event_id=AUDIT, observed_at=OBSERVED)


class SectionVersionValidateApiTests(unittest.TestCase):
    def setUp(self):
        self.validations = Validations()
        self.path = (f"/api/v1/projects/{PROJECT}/solution-sections/{SECTION}"
                     f"/versions/{VERSION}:validate")
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "v" * 16,
        }
        self.client = TestClient(create_app(
            solution_section_version_validate_router=create_section_version_validate_router(
                sessions=Sessions(),
                origins=LoginOriginPolicy(["https://plm.example.test"]),
                validations=self.validations)), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_six_dimension_report(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.path, headers=self.headers).status_code)
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual(data["observation_trace_id"], response.json()["trace_id"])
        self.assertEqual(data["audit_event_id"], str(AUDIT))
        self.assertEqual(data["solution_section_version_id"], str(VERSION))
        self.assertEqual(data["content_fingerprint"], (b"f" * 32).hex())
        self.assertEqual(data["observed_at"], "2026-10-12T00:00:00Z")
        self.assertEqual(data["facts"], {
            "integrity": "PASS", "content": "PASS", "requirements": "PASS",
            "evidence": "PASS", "trace": "UNAVAILABLE", "spec": "UNAVAILABLE"})
        self.assertTrue(data["valid"])
        self.assertFalse(data["ready_for_review"])
        self.assertEqual(data["issue_codes"], [
            "TRACE_COVERAGE_UNAVAILABLE", "STRUCTURED_SPEC_UNAVAILABLE"])

    def test_replay_keeps_observation_trace_but_new_request_trace(self):
        first = self.client.post(self.path, headers=self.headers).json()
        second_response = self.client.post(self.path, headers=self.headers)
        second = second_response.json()
        self.assertNotEqual(first["trace_id"], second["trace_id"])
        self.assertEqual(second["trace_id"], second_response.headers["x-trace-id"])
        self.assertEqual(first["data"], second["data"])

    def test_strict_auth_body_path_and_key(self):
        cases = (
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"}, None, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, None, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()}, None, 403),
            (self.path, {k: v for k, v in self.headers.items()
                         if k != "idempotency-key"}, None, 422),
            (self.path + "?scope=GLOBAL", self.headers, None, 400),
            (self.path, self.headers, "{}", 400),
            (self.path.replace(str(VERSION), "invalid"), self.headers, None, 422),
        )
        for path, headers, body, expected in cases:
            with self.subTest(path=path, expected=expected):
                response = self.client.post(path, headers=headers, content=body)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())

    def test_owner_errors_and_wrong_project_report_fail_closed(self):
        for code, expected in (
            ("RESOURCE_NOT_FOUND", 404), ("AUTH_ACCESS_DENIED", 404),
            ("PROJECT_ARCHIVED", 409), ("LICENSE_OPERATION_DENIED", 403),
            ("CONFLICT_IDEMPOTENCY", 409), ("SOLUTION_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.validations.error = code
                response = self.client.post(self.path, headers=self.headers)
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)
        self.validations.error = None
        self.validations.project = uuid.uuid4()
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers).status_code)


if __name__ == "__main__":
    unittest.main()
