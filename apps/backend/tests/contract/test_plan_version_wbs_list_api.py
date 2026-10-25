from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.list_plan_version_wbs import (
    create_plan_version_wbs_list_router,
)
from plm_assistant.modules.plan.api.wbs_list_cursor import PlanVersionWbsCursorCodec
from plm_assistant.modules.plan.application.list_plan_version_wbs import (
    PlanVersionWbsItemView, PlanVersionWbsPage, PlanVersionWbsReadError,
)


PROJECT, PLAN, VERSION, ITEM_1, ITEM_2 = (uuid.uuid4() for _ in range(5))
_DATA = {
    "wbs_item_id": str(ITEM_1), "parent_item_id": None,
    "wbs_code": "1", "name": "Root", "level": 1,
    "category": "IMPLEMENTATION", "owner_ref": None,
    "support_role_refs": ["PROJECT_MANAGER"],
    "planned_start": None, "planned_finish": None, "duration_minutes": 480,
    "actual_start": None, "actual_finish": None, "item_state": "NOT_STARTED",
    "entry_conditions": ["Ready"], "acceptance_criteria": ["Verified"],
    "requirement_refs": [], "solution_refs": [], "prototype_refs": [],
    "evidence_refs": [], "output_refs": [], "risk": None,
    "explicit_exclusion": None, "milestone_refs": [],
}


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    def __init__(self):
        self.calls = []
        self.error = None

    def list_current(self, query, *, plan_id, plan_version_id,
                     after_ordinal, after_wbs_item_id, limit):
        self.calls.append((query, plan_id, plan_version_id,
                           after_ordinal, after_wbs_item_id, limit))
        if self.error:
            raise PlanVersionWbsReadError(self.error)
        if after_ordinal is None:
            items = (PlanVersionWbsItemView(ITEM_1, 1, _DATA),)
            return PlanVersionWbsPage(
                plan_id, plan_version_id, PROJECT, items, 1, ITEM_1, True)
        return PlanVersionWbsPage(
            plan_id, plan_version_id, PROJECT,
            (PlanVersionWbsItemView(ITEM_2, 2, {**_DATA,
                                               "wbs_item_id": str(ITEM_2),
                                               "wbs_code": "1.1", "name": "Child",
                                               "parent_item_id": str(ITEM_1)}),),
            None, None, False)


class PlanVersionWbsListApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.path = f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions/{VERSION}/wbs-items"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
        }
        router = create_plan_version_wbs_list_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads,
            cursors=PlanVersionWbsCursorCodec(b"w" * 32),
        )
        self.client = TestClient(
            create_app(plan_version_wbs_list_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_bound_keyset_pages(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(
                self.path, headers=self.headers).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        data = first.json()["data"]
        self.assertTrue(data["has_more"])
        self.assertEqual(ITEM_1, uuid.UUID(data["items"][0]["wbs_item_id"]))
        cursor = data["next_cursor"]
        second = self.client.get(
            self.path + "?page_size=1&cursor=" + cursor, headers=self.headers)
        self.assertEqual(200, second.status_code)
        page2 = second.json()["data"]
        self.assertFalse(page2["has_more"])
        self.assertEqual(ITEM_2, uuid.UUID(page2["items"][0]["wbs_item_id"]))
        self.assertEqual(1, self.reads.calls[-1][3])
        self.assertEqual(ITEM_1, self.reads.calls[-1][4])

    def test_cursor_is_bound_and_query_is_closed(self):
        cursor = self.client.get(
            self.path + "?page_size=1", headers=self.headers).json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            self.path + "?page_size=2&cursor=" + cursor,
            headers=self.headers).status_code)
        self.assertEqual(400, self.client.get(
            self.path + "?page_size=1&other=1", headers=self.headers).status_code)
        self.assertEqual(400, self.client.get(
            self.path + "?page_size=1&page_size=1", headers=self.headers).status_code)
        self.assertEqual(422, self.client.get(
            self.path + "?page_size=201", headers=self.headers).status_code)

    def test_session_permission_license_and_resource_errors(self):
        self.assertEqual(401, self.client.get(
            self.path, headers={"origin": self.headers["origin"]}).status_code)
        self.assertEqual(403, self.client.get(
            self.path, headers={**self.headers, "origin": "https://evil.test"}).status_code)
        for code, status in (("RESOURCE_NOT_FOUND", 404),
                             ("AUTH_ACCESS_DENIED", 401),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("PLAN_UNAVAILABLE", 503)):
            self.reads.error = code
            with self.subTest(code=code):
                self.assertEqual(status, self.client.get(
                    self.path, headers=self.headers).status_code)


if __name__ == "__main__":
    unittest.main()
