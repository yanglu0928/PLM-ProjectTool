from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.validate_plan_version import (
    create_plan_version_validate_router,
)
from plm_assistant.modules.plan.application.validate_plan_version import (
    PlanVersionValidationError, ValidatePlanVersion,
)
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionCoverageSummary, PlanVersionValidationReport,
)


PROJECT, PLAN, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


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
        self.error = None
        self.report = PlanVersionValidationReport(
            valid=True, blocking_issues=(), warnings=(),
            coverage_summary=PlanVersionCoverageSummary(2, 1, 1, 0, 3, 2, 1, 0),
            checked_at=datetime(2026, 10, 26, 4, 5, 6, tzinfo=timezone.utc),
        )

    def validate(self, command):
        self.commands.append(command)
        if self.error:
            raise PlanVersionValidationError(self.error)
        return self.report


class PlanVersionValidateApiTests(unittest.TestCase):
    def setUp(self):
        self.validations = Validations()
        self.path = (
            f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions/{VERSION}:validate")
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "p" * 16,
        }
        router = create_plan_version_validate_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            validations=self.validations,
        )
        self.client = TestClient(
            create_app(plan_version_validation_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_exact_report_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.path, headers=self.headers).status_code)
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "valid": True, "blocking_issues": [], "warnings": [],
            "coverage_summary": {
                "requirement_total": 2, "requirement_mapped": 1,
                "requirement_excluded": 1, "requirement_uncovered": 0,
                "solution_total": 3, "solution_mapped": 2,
                "solution_excluded": 1, "solution_uncovered": 0,
            },
            "checked_at": "2026-10-26T04:05:06Z",
        }, response.json()["data"])
        command = self.validations.commands[-1]
        self.assertIs(type(command), ValidatePlanVersion)
        self.assertEqual((PROJECT, PLAN, VERSION),
                         (command.project_id, command.plan_id,
                          command.plan_version_id))
        self.assertEqual(b"s" * 32, command.session_token)
        self.assertEqual(b"c" * 32, command.csrf_token)
        self.assertEqual("p" * 16, command.idempotency_key)

    def test_auth_headers_and_request_shape_fail_closed(self):
        cases = (
            ({k: v for k, v in self.headers.items() if k != "cookie"}, None, 401),
            ({**self.headers, "origin": "https://evil.test"}, None, 403),
            ({**self.headers, "x-csrf-token": (b"x" * 32).hex()}, None, 403),
            ({k: v for k, v in self.headers.items()
              if k != "idempotency-key"}, None, 422),
            (self.headers, "?q=1", 400),
            (self.headers, "body", 400),
        )
        for headers, suffix, expected in cases:
            with self.subTest(expected=expected, suffix=suffix):
                response = self.client.post(
                    self.path + (suffix if suffix and suffix.startswith("?") else ""),
                    headers=headers,
                    content=(suffix.encode() if suffix == "body" else None),
                )
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())

    def test_path_and_owner_errors_use_stable_envelope(self):
        bad_path = self.path.replace(str(VERSION), str(VERSION).upper())
        malformed = self.client.post(bad_path, headers=self.headers)
        self.assertEqual(422, malformed.status_code)
        self.assertEqual([], self.validations.commands)

        for code, status, response_code in (
            ("RESOURCE_NOT_FOUND", 404, "RESOURCE_NOT_FOUND"),
            ("LICENSE_OPERATION_DENIED", 403, "LICENSE_OPERATION_DENIED"),
            ("CONFLICT_IDEMPOTENCY", 409, "CONFLICT_IDEMPOTENCY"),
            ("VALIDATION_FAILED", 422, "VALIDATION_FAILED"),
            ("PLAN_UNAVAILABLE", 503, "SYSTEM_UNAVAILABLE"),
        ):
            with self.subTest(code=code):
                self.validations.error = code
                response = self.client.post(self.path, headers=self.headers)
                self.assertEqual(status, response.status_code)
                self.assertEqual(response_code, response.json()["error"]["code"])


if __name__ == "__main__":
    unittest.main()
