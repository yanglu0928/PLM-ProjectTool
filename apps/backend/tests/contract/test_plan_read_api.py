"""Frozen PLAN_GET opt-in HTTP shape and closed defaults."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.read_plan import create_plan_read_router
from plm_assistant.modules.plan.application.read_plan import (
    PlanCurrentView, PlanReadError,
)


PROJECT, PLAN, ACTOR = (uuid.uuid4() for _ in range(3))
VIEW = PlanCurrentView(
    PLAN, PROJECT, "Current plan", "ACTIVE", None, ACTOR,
    datetime(2026, 10, 19, tzinfo=timezone.utc), '"v0"')


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    def __init__(self):
        self.queries = []
        self.error = None
        self.view = VIEW

    def get_current(self, query, plan_id):
        self.queries.append((query, plan_id))
        if self.error:
            raise PlanReadError(self.error)
        return self.view


class PlanReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        router = create_plan_read_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads)
        self.client = TestClient(
            create_app(plan_read_router=router), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_detail_shape(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v0"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "plan_id": str(PLAN), "project_id": str(PROJECT), "name": "Current plan",
            "plan_state": "ACTIVE", "current_approved_version_ref": None,
            "created_by": str(ACTOR), "created_at": "2026-10-19T00:00:00Z",
            "etag": '"v0"',
        }, response.json()["data"])
        query, identity = self.reads.queries[-1]
        self.assertEqual((query.project_id, identity), (PROJECT, PLAN))
        self.assertEqual(query.session_token, b"s" * 32)

    def test_auth_host_path_and_query(self):
        cases = (
            (self.path, {}, 401),
            (self.path, {**self.headers, "host": "evil.test"}, 403),
            (self.path + "?scope=GLOBAL", self.headers, 400),
            (f"/api/v1/projects/{str(PROJECT).upper()}/plans/{PLAN}", self.headers, 422),
            (f"/api/v1/projects/{PROJECT}/plans/{str(PLAN).upper()}", self.headers, 422),
        )
        for path, headers, expected in cases:
            with self.subTest(path=path, expected=expected):
                self.assertEqual(expected, self.client.get(path, headers=headers).status_code)
        self.assertFalse(self.reads.queries)

    def test_errors_and_projection_fail_closed(self):
        for code, expected in (
            ("AUTH_ACCESS_DENIED", 401), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("PLAN_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.reads.error = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)
        self.reads.error = None
        self.reads.view = replace(VIEW, current_approved_version_ref=uuid.uuid4())
        self.assertEqual(503, self.client.get(self.path, headers=self.headers).status_code)


if __name__ == "__main__":
    unittest.main()
