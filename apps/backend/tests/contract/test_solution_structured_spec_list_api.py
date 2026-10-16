"""Signed StructuredSpec version-list cursor and opt-in HTTP contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.structured_spec_list import create_structured_spec_list_router
from plm_assistant.modules.solution.api.structured_spec_list_cursor import StructuredSpecListCursorCodec
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecListPage, StructuredSpecReadError, StructuredSpecSummaryView,
)


PROJECT, FIRST, SECOND, ACTOR = (uuid.uuid4() for _ in range(4))
FIRST, SECOND = sorted((FIRST, SECOND), key=lambda value: value.int, reverse=True)
NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
ITEMS = (
    StructuredSpecSummaryView(
        FIRST, uuid.uuid4(), PROJECT, "MIGRATION_SPEC", 1, "DRAFT",
        b"a" * 32, b"b" * 32, None, None, None, ACTOR, NOW),
    StructuredSpecSummaryView(
        SECOND, uuid.uuid4(), PROJECT, "INTERFACE_SPEC", 1, "APPROVED",
        b"c" * 32, b"d" * 32, None, uuid.uuid4(), uuid.uuid4(), ACTOR, NOW),
)


class Sessions:
    def validate(self, token):
        if token not in (b"s" * 32, b"t" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    error = None
    broken = False

    def list_versions(self, query, *, before_spec_id, limit):
        if self.error:
            raise StructuredSpecReadError(self.error)
        if self.broken:
            return StructuredSpecListPage((ITEMS[0],), None, True)
        selected = tuple(item for item in ITEMS
                         if before_spec_id is None
                         or item.structured_solution_spec_id.int < before_spec_id.int)
        page = selected[:limit]
        more = len(selected) > limit
        return StructuredSpecListPage(
            page, page[-1].structured_solution_spec_id if more else None, more)


class StructuredSpecListApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.codec = StructuredSpecListCursorCodec(b"x" * 32)
        self.path = f"/api/v1/projects/{PROJECT}/structured-solution-specs"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_structured_spec_list_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec)
        self.client = TestClient(
            create_app(solution_structured_spec_list_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_two_pages_and_safe_summary(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        self.assertEqual(404, self.client.post(
            self.path, headers=self.headers).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        self.assertEqual(first.headers["x-trace-id"], first.json()["trace_id"])
        page = first.json()["data"]
        self.assertTrue(page["has_more"])
        item = page["items"][0]
        self.assertEqual({
            "structured_solution_spec_id": str(FIRST),
            "spec_series_id": str(ITEMS[0].spec_series_id),
            "project_id": str(PROJECT), "spec_type": "MIGRATION_SPEC",
            "version_no": 1, "version_state": "DRAFT",
            "content_fingerprint": "61" * 32,
            "payload_fingerprint": "62" * 32,
            "supersedes_version_ref": None, "review_ref": None,
            "review_round_ref": None, "created_by": str(ACTOR),
            "created_at": "2026-10-16T00:00:00Z",
        }, item)
        cursor = page["next_cursor"]
        self.assertNotIn(str(FIRST), cursor)
        second = self.client.get(
            self.path, params={"page_size": "1", "cursor": cursor},
            headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertEqual(str(SECOND), second.json()["data"]["items"][0][
            "structured_solution_spec_id"])
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertIsNone(second.json()["data"]["next_cursor"])

    def test_cursor_request_and_output_rejections(self):
        cursor = self.codec.encode(
            session_token=b"s" * 32, project_id=PROJECT,
            page_size=1, before_spec_id=FIRST)
        variants = (
            (self.path + "?page_size=2&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=1&cursor=A" + cursor[1:], self.headers, 400),
            (self.path + "?cursor=" + cursor + "&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=0", self.headers, 422),
            (self.path + "?after=" + str(FIRST), self.headers, 400),
            (self.path + "?page_size=1&cursor=" + cursor,
             {**self.headers, "cookie": "plm_session=" + (b"t" * 32).hex()}, 400),
            (f"/api/v1/projects/{uuid.uuid4()}/structured-solution-specs"
             "?page_size=1&cursor=" + cursor, self.headers, 400),
            (self.path, {}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403),
        )
        for path, headers, expected in variants:
            with self.subTest(path=path):
                self.assertEqual(expected,
                                 self.client.get(path, headers=headers).status_code)
        self.reads.broken = True
        self.assertEqual(503, self.client.get(
            self.path, headers=self.headers).status_code)

    def test_owner_failures(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("AUTH_ACCESS_DENIED", 401),
                               ("SOLUTION_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.reads.error = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
