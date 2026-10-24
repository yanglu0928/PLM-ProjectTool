"""Frozen PLAN_LIST signed keyset cursor and opt-in HTTP shape."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from fastapi import APIRouter

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec
from plm_assistant.modules.plan.api.list_plan import create_plan_list_router
from plm_assistant.modules.plan.application.read_plan import (
    PlanListPage, PlanReadError, PlanSummaryView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError


PROJECT = uuid.uuid4()
FIRST, SECOND = sorted((uuid.uuid4(), uuid.uuid4()), key=lambda value: value.int,
                       reverse=True)
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
ITEMS = (
    PlanSummaryView(FIRST, PROJECT, "First", "ACTIVE", None, NOW, '"v0"'),
    PlanSummaryView(SECOND, PROJECT, "Second", "ACTIVE", None, NOW, '"v0"'),
)


class Sessions:
    def validate(self, token):
        if token not in (b"s" * 32, b"t" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    def __init__(self):
        self.calls = []
        self.error = None
        self.items = ITEMS

    def list_current(self, query, *, after_created_at, after_plan_id, limit):
        self.calls.append((query, after_created_at, after_plan_id, limit))
        if self.error:
            raise PlanReadError(self.error)
        selected = tuple(item for item in self.items if after_created_at is None
                         or (item.created_at, item.plan_id.int)
                         < (after_created_at, after_plan_id.int))
        page = selected[:limit]
        more = len(selected) > limit
        return PlanListPage(page, page[-1].created_at if more else None,
                            page[-1].plan_id if more else None, more)


class PlanListApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.codec = PlanListCursorCodec(b"p" * 32)
        self.path = f"/api/v1/projects/{PROJECT}/plans"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_plan_list_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec)
        self.client = TestClient(create_app(plan_list_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_two_pages_tied_timestamp_and_summary(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        self.assertEqual(404, self.client.post(self.path, headers=self.headers).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        self.assertEqual(first.headers["x-trace-id"], first.json()["trace_id"])
        data = first.json()["data"]
        self.assertTrue(data["has_more"])
        self.assertEqual([{
            "plan_id": str(FIRST), "project_id": str(PROJECT), "name": "First",
            "plan_state": "ACTIVE", "current_approved_version_ref": None,
            "created_at": "2026-10-19T00:00:00Z", "etag": '"v0"',
        }], data["items"])
        cursor = data["next_cursor"]
        self.assertNotIn(str(FIRST), cursor)
        second = self.client.get(self.path, params={"page_size": "1", "cursor": cursor},
                                 headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertEqual(str(SECOND), second.json()["data"]["items"][0]["plan_id"])
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertIsNone(second.json()["data"]["next_cursor"])
        self.assertEqual((NOW, FIRST), self.reads.calls[-1][1:3])

    def test_default_page_size_max_and_rejections(self):
        self.assertEqual(200, self.client.get(self.path, headers=self.headers).status_code)
        self.assertEqual(50, self.reads.calls[-1][3])
        self.assertEqual(200, self.client.get(
            self.path + "?page_size=200", headers=self.headers).status_code)
        self.assertEqual(200, self.reads.calls[-1][3])
        cursor = self.codec.encode(session_token=b"s" * 32, project_id=PROJECT,
                                   page_size=1, created_at=NOW, plan_id=FIRST)
        variants = (
            (self.path + "?page_size=2&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=1&cursor=A" + cursor[1:], self.headers, 400),
            (self.path + "?cursor=" + cursor + "&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=0", self.headers, 422),
            (self.path + "?page_size=201", self.headers, 422),
            (self.path + "?page_size=01", self.headers, 422),
            (self.path + "?after=" + str(FIRST), self.headers, 400),
            (self.path + "?page_size=1&cursor=" + cursor,
             {**self.headers, "cookie": "plm_session=" + (b"t" * 32).hex()}, 400),
            (f"/api/v1/projects/{uuid.uuid4()}/plans?page_size=1&cursor=" + cursor,
             self.headers, 400),
            (self.path, {}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403),
        )
        before = len(self.reads.calls)
        for path, headers, expected in variants:
            with self.subTest(path=path):
                self.assertEqual(expected, self.client.get(path, headers=headers).status_code)
        self.assertEqual(before, len(self.reads.calls))

    def test_owner_failure_and_projection_fail_closed(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("AUTH_ACCESS_DENIED", 401),
                               ("PLAN_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.reads.error = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)
        self.reads.error = None
        self.reads.items = (replace(ITEMS[0], current_approved_version_ref=uuid.uuid4()),)
        self.assertEqual(503, self.client.get(self.path, headers=self.headers).status_code)

    def test_codec_rejects_invalid_key_and_tampering(self):
        with self.assertRaises(ValueError):
            PlanListCursorCodec(b"weak")
        token = self.codec.encode(session_token=b"s" * 32, project_id=PROJECT,
                                  page_size=1, created_at=NOW, plan_id=FIRST)
        for candidate in (token + "!", "A" + token[1:], "", token.replace(".", "..")):
            with self.subTest(candidate=candidate[:8]), self.assertRaises(ApplicationError):
                self.codec.decode(candidate, session_token=b"s" * 32,
                                  project_id=PROJECT, page_size=1)

    def test_create_router_precedes_read_only_post_guard(self):
        create = APIRouter()

        @create.post("/api/v1/projects/{project_id}/plans")
        async def create_stub(project_id: str):
            return {"source": "create", "project_id": project_id}

        listing = create_plan_list_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec)
        with TestClient(create_app(plan_create_router=create, plan_list_router=listing),
                        base_url="https://plm.example.test") as client:
            response = client.post(self.path)
            self.assertEqual(200, response.status_code)
            self.assertEqual("create", response.json()["source"])


if __name__ == "__main__":
    unittest.main()
