from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.read_plan_version import (
    create_plan_version_read_router,
)
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionReadError, PlanVersionReadQuery, PlanVersionSnapshotView,
)


PROJECT, PLAN, VERSION, ACTOR = (uuid.uuid4() for _ in range(4))
SNAPSHOT = {
    "calendar_ref": "CN_WORKDAY", "approved_solution_refs": [],
    "wbs_items": [], "dependencies": [], "milestones": [], "exclusions": [],
}


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    def __init__(self):
        self.queries = []
        self.error = None
        self.result_project = PROJECT

    def get_current(self, query, *, plan_id, plan_version_id):
        self.queries.append((query, plan_id, plan_version_id))
        if self.error:
            raise PlanVersionReadError(self.error)
        return PlanVersionSnapshotView(
            VERSION, PLAN, self.result_project, 2, "DRAFT", ACTOR,
            datetime(2026, 10, 26, tzinfo=timezone.utc), None, None, None, SNAPSHOT,
        )


class PlanVersionReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions/{VERSION}"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
        }
        router = create_plan_version_read_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads,
        )
        self.client = TestClient(
            create_app(plan_version_read_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_complete_snapshot_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "plan_version_id": str(VERSION), "plan_id": str(PLAN),
            "project_id": str(PROJECT), "version_no": 2,
            "version_state": "DRAFT", "created_by": str(ACTOR),
            "supersedes_version_ref": None, "review_ref": None,
            "review_round_ref": None,
            "created_at": "2026-10-26T00:00:00Z", **SNAPSHOT,
        }, response.json()["data"])
        query, plan, version = self.reads.queries[-1]
        self.assertEqual((PLAN, VERSION), (plan, version))
        self.assertIs(type(query), PlanVersionReadQuery)
        self.assertEqual(b"s" * 32, query.session_token)

    def test_session_origin_path_and_query_boundaries(self):
        self.assertEqual(401, self.client.get(
            self.path, headers={"origin": self.headers["origin"]}).status_code)
        self.assertEqual(403, self.client.get(
            self.path, headers={**self.headers, "origin": "https://evil.test"}).status_code)
        self.assertEqual(400, self.client.get(
            self.path + "?latest=true", headers=self.headers).status_code)
        self.assertEqual(422, self.client.get(
            f"/api/v1/projects/{PROJECT}/plans/not-a-uuid/versions/{VERSION}",
            headers=self.headers).status_code)

    def test_error_projection_and_wrong_project_view_fails_closed(self):
        for code, expected in (
            ("RESOURCE_NOT_FOUND", 404), ("AUTH_ACCESS_DENIED", 401),
            ("LICENSE_OPERATION_DENIED", 403), ("VALIDATION_FAILED", 422),
            ("PLAN_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.reads.error = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)
        self.reads.error = None
        self.reads.result_project = uuid.uuid4()
        self.assertEqual(503, self.client.get(
            self.path, headers=self.headers).status_code)


if __name__ == "__main__":
    unittest.main()
