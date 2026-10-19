"""Frozen SOL_SPEC_VALIDATE opt-in HTTP projection contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.structured_spec_validate import (
    create_structured_spec_validate_router,
)
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    StructuredSpecValidationFacts, StructuredSpecValidationObservation,
    StructuredSpecValidationSnapshot, build_structured_spec_type_checks,
    build_structured_spec_validation_report,
)
from plm_assistant.modules.solution.application.validate_structured_spec import (
    StructuredSpecValidationError,
)


PROJECT, SPEC, SERIES, AUDIT = (uuid.uuid4() for _ in range(4))
OBSERVED = datetime(2026, 10, 19, tzinfo=timezone.utc)


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
            raise StructuredSpecValidationError(self.error)
        if self.first_trace is None:
            self.first_trace = command.trace_id
        replay = command.__class__(
            command.session_token, command.csrf_token, self.first_trace,
            self.project, command.structured_solution_spec_id,
            command.idempotency_key)
        observation = StructuredSpecValidationObservation(
            StructuredSpecValidationFacts(
                "PASS", "PASS", "PASS", "PASS", "PASS", "PASS",
                "UNAVAILABLE", "PASS"),
            build_structured_spec_type_checks("MIGRATION_SPEC", {
                "SCOPE_MAPPING": "PASS",
                "TRIAL_PLAN": "PASS",
                "RECONCILIATION_PLAN": "PASS",
                "ROLLBACK_PLAN": "PASS",
                "ACCEPTANCE_CRITERIA": "PASS",
            }))
        return build_structured_spec_validation_report(
            replay, StructuredSpecValidationSnapshot(
                self.project, command.structured_solution_spec_id, SERIES,
                "MIGRATION_SPEC", 2, "DRAFT", b"c" * 32, b"p" * 32,
                1, 1, 1, 0),
            observation, audit_event_id=AUDIT, observed_at=OBSERVED)


class StructuredSpecValidateApiTests(unittest.TestCase):
    def setUp(self):
        self.validations = Validations()
        self.path = (
            f"/api/v1/projects/{PROJECT}/structured-solution-specs/"
            f"{SPEC}:validate")
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "structured-spec-http-0001",
        }
        self.client = TestClient(create_app(
            solution_structured_spec_validate_router=(
                create_structured_spec_validate_router(
                    sessions=Sessions(),
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                    validations=self.validations))),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_complete_type_specific_report(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(
                404, bare.post(self.path, headers=self.headers).status_code)
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual(data["observation_trace_id"], response.json()["trace_id"])
        self.assertEqual(data["audit_event_id"], str(AUDIT))
        self.assertEqual(data["structured_solution_spec_id"], str(SPEC))
        self.assertEqual(data["spec_series_id"], str(SERIES))
        self.assertEqual(data["spec_type"], "MIGRATION_SPEC")
        self.assertEqual(data["version_no"], 2)
        self.assertEqual(data["content_fingerprint"], (b"c" * 32).hex())
        self.assertEqual(data["payload_fingerprint"], (b"p" * 32).hex())
        self.assertEqual(data["facts"], {
            "integrity": "PASS", "payload": "PASS",
            "requirements": "PASS", "sections": "PASS",
            "evidence": "PASS", "artifacts": "PASS",
            "trace": "UNAVAILABLE", "current_version": "PASS"})
        self.assertEqual(data["type_checks"][0], {
            "code": "SCOPE_MAPPING", "status": "PASS"})
        self.assertTrue(data["valid"])
        self.assertFalse(data["ready_for_review"])
        self.assertIn("TRACE_COVERAGE_UNAVAILABLE", data["issue_codes"])
        self.assertEqual(data["observed_at"], "2026-10-19T00:00:00Z")

    def test_replay_keeps_observation_trace_but_new_request_trace(self):
        first = self.client.post(self.path, headers=self.headers).json()
        second_response = self.client.post(self.path, headers=self.headers)
        second = second_response.json()
        self.assertNotEqual(first["trace_id"], second["trace_id"])
        self.assertEqual(second["trace_id"], second_response.headers["x-trace-id"])
        self.assertEqual(first["data"], second["data"])

    def test_strict_auth_empty_body_path_query_and_key(self):
        cases = (
            (self.path, {key: value for key, value in self.headers.items()
                         if key != "cookie"}, None, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, None, 403),
            (self.path, {**self.headers,
                         "x-csrf-token": (b"x" * 32).hex()}, None, 403),
            (self.path, {key: value for key, value in self.headers.items()
                         if key != "idempotency-key"}, None, 422),
            (self.path + "?scope=GLOBAL", self.headers, None, 400),
            (self.path, self.headers, "{}", 400),
            (self.path.replace(str(SPEC), "invalid"), self.headers, None, 422),
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
        self.assertEqual(
            503, self.client.post(self.path, headers=self.headers).status_code)


if __name__ == "__main__":
    unittest.main()
