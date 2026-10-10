"""Signed PROJECT Reference List cursor and HTTP envelope contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.reference_list import create_project_reference_list_router
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceListPage, ReferenceReadError, ReferenceSummaryView,
)


PROJECT, FIRST, SECOND, VERSION1, VERSION2 = (uuid.uuid4() for _ in range(5))
FIRST, SECOND = sorted((FIRST, SECOND), key=lambda value: value.int)
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
ITEMS = (
    ReferenceSummaryView(FIRST, VERSION1, PROJECT, "First", "REFERENCE_ONLY",
                         1, "DRAFT", NOW, '"v0"'),
    ReferenceSummaryView(SECOND, VERSION2, PROJECT, "Second", "REFERENCE_ONLY",
                         1, "DRAFT", NOW, '"v0"'),
)


class Sessions:
    def validate(self, token):
        if token not in (b"s" * 32, b"t" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    error = None

    def list_current(self, query, *, after_reference_solution_id, limit):
        if self.error:
            raise ReferenceReadError(self.error)
        selected = tuple(item for item in ITEMS
                         if after_reference_solution_id is None
                         or item.reference_solution_id.int > after_reference_solution_id.int)
        page = selected[:limit]
        more = len(selected) > limit
        return ReferenceListPage(
            page, page[-1].reference_solution_id if more else None, more)


class ReferenceListApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.codec = ReferenceListCursorCodec(b"k" * 32)
        self.path = f"/api/v1/projects/{PROJECT}/reference-solutions"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_project_reference_list_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec)
        self.client = TestClient(
            create_app(project_reference_list_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_opt_in_two_pages_and_safe_summary(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        self.assertEqual(first.headers["x-trace-id"], first.json()["trace_id"])
        page = first.json()["data"]
        self.assertTrue(page["has_more"])
        self.assertEqual([str(FIRST)], [item["reference_solution_id"]
                                       for item in page["items"]])
        self.assertNotIn("document_version_ids", page["items"][0])
        self.assertNotIn("source_fingerprint", page["items"][0])
        cursor = page["next_cursor"]
        self.assertNotIn(str(FIRST), cursor)
        second = self.client.get(self.path, params={"page_size": "1", "cursor": cursor},
                                 headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertEqual(str(SECOND),
                         second.json()["data"]["items"][0]["reference_solution_id"])
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertIsNone(second.json()["data"]["next_cursor"])

    def test_cursor_bindings_and_query_errors(self):
        cursor = self.codec.encode(session_token=b"s" * 32, project_id=PROJECT,
                                   page_size=1, reference_solution_id=FIRST)
        variants = (
            (self.path + "?page_size=2&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=1&cursor=A" + cursor[1:], self.headers, 400),
            (self.path + "?cursor=" + cursor + "&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=0", self.headers, 422),
            (self.path + "?after=" + str(FIRST), self.headers, 400),
            (self.path + "?page_size=1&cursor=" + cursor,
             {**self.headers, "cookie": "plm_session=" + (b"t" * 32).hex()}, 400),
            (f"/api/v1/projects/{uuid.uuid4()}/reference-solutions"
             "?page_size=1&cursor=" + cursor, self.headers, 400),
            (self.path, {}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403),
        )
        for path, headers, expected in variants:
            with self.subTest(expected=expected, path=path):
                self.assertEqual(expected,
                                 self.client.get(path, headers=headers).status_code)
        self.assertEqual(404, self.client.get(
            "/api/v1/global/reference-solutions", headers=self.headers).status_code)

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
