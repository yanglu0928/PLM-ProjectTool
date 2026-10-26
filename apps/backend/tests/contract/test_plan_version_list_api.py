from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.list_plan_versions import create_plan_version_list_router
from plm_assistant.modules.plan.api.version_list_cursor import PlanVersionListCursorCodec
from plm_assistant.modules.plan.application.list_plan_versions import (
    PlanVersionListError, PlanVersionListPage, PlanVersionSummary,
)

PROJECT, PLAN = uuid.uuid4(), uuid.uuid4()
V1, V2 = uuid.uuid4(), uuid.uuid4()
CREATOR = uuid.uuid4()


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")


class Reads:
    def __init__(self):
        self.calls = []

    def list_current(self, query, *, plan_id, after_version_no, limit):
        self.calls.append((query.project_id, plan_id, after_version_no, limit))
        now = datetime(2026, 10, 26, tzinfo=timezone.utc)
        if after_version_no is None:
            return PlanVersionListPage((PlanVersionSummary(
                V2, PLAN, PROJECT, 2, "DRAFT", None, None, None, CREATOR, now),), 2, True)
        return PlanVersionListPage((PlanVersionSummary(
            V1, PLAN, PROJECT, 1, "SUPERSEDED", V2, uuid.uuid4(), uuid.uuid4(),
            CREATOR, now),), None, False)


class PlanVersionListApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.codec = PlanVersionListCursorCodec(b"k" * 32)
        router = create_plan_version_list_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec)
        self.client = TestClient(create_app(plan_version_list_router=router),
                                 base_url="https://plm.example.test")
        self.path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}

    def test_paginates_descending_and_binds_cursor_scope(self):
        first = self.client.get(self.path, params={"page_size": "1"}, headers=self.headers)
        self.assertEqual(first.status_code, 200)
        body = first.json()["data"]
        self.assertEqual([row["version_no"] for row in body["items"]], [2])
        self.assertTrue(body["has_more"])
        second = self.client.get(self.path, params={
            "page_size": "1", "cursor": body["next_cursor"]}, headers=self.headers)
        self.assertEqual(second.status_code, 200)
        self.assertEqual([row["version_no"] for row in second.json()["data"]["items"]], [1])
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertEqual([call[2] for call in self.reads.calls], [None, 2])
        for changed in ({"plan_id": uuid.uuid4()}, {"project_id": uuid.uuid4()}):
            path = f"/api/v1/projects/{changed.get('project_id', PROJECT)}/plans/{changed.get('plan_id', PLAN)}/versions"
            rejected = self.client.get(path, params={
                "page_size": "1", "cursor": body["next_cursor"]}, headers=self.headers)
            self.assertEqual(rejected.status_code, 400)

    def test_default_app_does_not_mount_contract_operation(self):
        response = TestClient(create_app()).get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_unknown_or_duplicate_query_is_rejected(self):
        for query in ("page_size=1&page_size=2", "limit=1", "page_size=201"):
            response = self.client.get(self.path + "?" + query, headers=self.headers)
            self.assertIn(response.status_code, (400, 422))

    def test_service_error_does_not_leak_internal_details(self):
        class Denied:
            def list_current(self, *args, **kwargs):
                raise PlanVersionListError("LICENSE_OPERATION_DENIED")
        router = create_plan_version_list_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=Denied(), cursors=self.codec)
        response = TestClient(create_app(plan_version_list_router=router)).get(
            self.path, headers=self.headers)
        self.assertEqual(response.status_code, 403)
