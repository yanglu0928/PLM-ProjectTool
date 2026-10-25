from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.create_plan_version import (
    create_plan_version_create_router,
)
from plm_assistant.modules.plan.application.create_plan_version import (
    PlanVersionCreateError, PlanVersionCreatedView,
)


PROJECT, PLAN, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


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

    def create(self, command):
        self.commands.append(command)
        if self.error:
            raise PlanVersionCreateError(self.error)
        return PlanVersionCreatedView(
            VERSION, PLAN, PROJECT, 2, "DRAFT",
            datetime(2026, 10, 26, tzinfo=timezone.utc),
        )


class PlanVersionCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.creates = Creates()
        self.path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "p" * 16,
        }
        router = create_plan_version_create_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            creates=self.creates,
        )
        self.client = TestClient(
            create_app(plan_version_create_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_created_contract(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.path, headers=self.headers, json={}).status_code)
        response = self.client.post(self.path, headers=self.headers, json={})
        self.assertEqual(201, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(f"{self.path}/{VERSION}", response.headers["location"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "plan_version_id": str(VERSION), "plan_id": str(PLAN),
            "project_id": str(PROJECT), "version_no": 2,
            "version_state": "DRAFT", "created_at": "2026-10-26T00:00:00Z",
        }, response.json()["data"])
        self.assertEqual(PROJECT, self.creates.commands[-1].project_id)
        self.assertEqual(PLAN, self.creates.commands[-1].plan_id)
        self.assertEqual({}, self.creates.commands[-1].draft)
        self.assertEqual(b"s" * 32, self.creates.commands[-1].session_token)
        self.assertEqual(b"c" * 32, self.creates.commands[-1].csrf_token)

    def test_auth_scope_and_strict_json_boundary(self):
        cases = (
            ({k: v for k, v in self.headers.items() if k != "cookie"}, {}, 401),
            ({**self.headers, "origin": "https://evil.test"}, {}, 403),
            ({**self.headers, "x-csrf-token": (b"x" * 32).hex()}, {}, 403),
            ({k: v for k, v in self.headers.items() if k != "idempotency-key"}, {}, 422),
        )
        for headers, body, expected in cases:
            with self.subTest(expected=expected):
                response = self.client.post(self.path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())
        self.assertEqual(400, self.client.post(
            self.path + "?query=forbidden", headers=self.headers, json={}).status_code)
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"x":1,"x":2}').status_code)
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers, json=[]).status_code)
        self.assertEqual(422, self.client.post(
            f"/api/v1/projects/not-a-uuid/plans/{PLAN}/versions",
            headers=self.headers, json={}).status_code)

    def test_public_error_projection(self):
        for code, expected in (
            ("RESOURCE_NOT_FOUND", 404), ("AUTH_ACCESS_DENIED", 404),
            ("PROJECT_ARCHIVED", 409),
            ("LICENSE_OPERATION_DENIED", 403),
            ("CONFLICT_IDEMPOTENCY", 409),
            ("PLAN_SOURCE_UNAVAILABLE", 404),
            ("OUTPUT_REFERENCE_UNAVAILABLE", 422),
            ("VALIDATION_FAILED", 422), ("PLAN_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.creates.error = code
                response = self.client.post(self.path, headers=self.headers, json={})
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)

    def test_wrong_owner_response_fails_closed(self):
        self.creates.create = lambda _: PlanVersionCreatedView(
            VERSION, PLAN, uuid.uuid4(), 2, "DRAFT",
            datetime(2026, 10, 26, tzinfo=timezone.utc))
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json={}).status_code)


if __name__ == "__main__":
    unittest.main()
