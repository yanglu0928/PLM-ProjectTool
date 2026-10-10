"""GLOBAL Reference List signed cursor, safe summary and HTTP errors."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.global_reference_list import create_global_reference_list_router
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.application.read_global_reference import (
    GlobalReferenceListPage, GlobalReferenceReadError, GlobalReferenceSummaryView,
)


FIRST, SECOND, VERSION1, VERSION2 = (uuid.uuid4() for _ in range(4))
FIRST, SECOND = sorted((FIRST, SECOND), key=lambda value: value.int)
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
ITEMS = (
    GlobalReferenceSummaryView(FIRST, VERSION1, "First", "REFERENCE_ONLY",
                               1, "DRAFT", NOW, '"v0"'),
    GlobalReferenceSummaryView(SECOND, VERSION2, "Second", "REFERENCE_ONLY",
                               1, "DRAFT", NOW, '"v0"'),
)


class Sessions:
    def validate(self, token):
        if token not in (b"s" * 32, b"t" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")


class Reads:
    error = None

    def list_current(self, query, *, after_reference_solution_id, limit):
        if self.error:
            raise GlobalReferenceReadError(self.error)
        selected = tuple(item for item in ITEMS if after_reference_solution_id is None
                         or item.reference_solution_id.int
                         > after_reference_solution_id.int)
        page = selected[:limit]
        has_more = len(selected) > limit
        return GlobalReferenceListPage(
            page, page[-1].reference_solution_id if has_more else None,
            has_more)


class GlobalReferenceListTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.codec = GlobalReferenceListCursorCodec(b"g" * 32)
        self.path = "/api/v1/global/reference-solutions"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_global_reference_list_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec)
        self.client = TestClient(create_app(global_reference_list_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_opt_in_two_pages_and_read_only_post(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        page = first.json()["data"]
        self.assertTrue(page["has_more"])
        self.assertEqual(str(FIRST), page["items"][0]["reference_solution_id"])
        self.assertEqual("GLOBAL", page["items"][0]["scope"])
        self.assertIsNone(page["items"][0]["project_id"])
        self.assertNotIn("document_refs", page["items"][0])
        self.assertNotIn("deidentification_confirmation_id", page["items"][0])
        cursor = page["next_cursor"]
        self.assertNotIn(str(FIRST), cursor)
        second = self.client.get(self.path, params={"page_size": "1", "cursor": cursor},
                                 headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertEqual(str(SECOND), second.json()["data"]["items"][0]["reference_solution_id"])
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertIsNone(second.json()["data"]["next_cursor"])
        self.assertEqual(404, self.client.post(self.path, headers=self.headers).status_code)

    def test_cursor_family_session_page_and_query_fail_closed(self):
        cursor = self.codec.encode(session_token=b"s" * 32, page_size=1,
                                   reference_solution_id=FIRST)
        project_cursor = ReferenceListCursorCodec(b"g" * 32).encode(
            session_token=b"s" * 32, project_id=uuid.uuid4(), page_size=1,
            reference_solution_id=FIRST)
        variants = (
            (self.path + "?page_size=2&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=1&cursor=A" + cursor[1:], self.headers, 400),
            (self.path + "?page_size=1&cursor=" + project_cursor, self.headers, 400),
            (self.path + "?page_size=1&cursor=" + cursor,
             {**self.headers, "cookie": "plm_session=" + (b"t" * 32).hex()}, 400),
            (self.path + "?cursor=" + cursor + "&cursor=" + cursor, self.headers, 400),
            (self.path + "?page_size=0", self.headers, 422),
            (self.path + "?after=" + str(FIRST), self.headers, 400),
            (self.path, {}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403),
        )
        for path, headers, expected in variants:
            with self.subTest(expected=expected, path=path[:85]):
                self.assertEqual(expected, self.client.get(path, headers=headers).status_code)
        self.reads.error = "LICENSE_OPERATION_DENIED"
        self.assertEqual(403, self.client.get(self.path, headers=self.headers).status_code)
        self.reads.error = "RESOURCE_NOT_FOUND"
        self.assertEqual(404, self.client.get(self.path, headers=self.headers).status_code)

    def test_codec_rejects_missing_key_and_recovery_changes(self):
        with self.assertRaises(ValueError):
            GlobalReferenceListCursorCodec(b"short")
        token = self.codec.encode(session_token=b"s" * 32, page_size=25,
                                  reference_solution_id=FIRST)
        self.assertEqual(FIRST, self.codec.decode(
            token, session_token=b"s" * 32, page_size=25))
        with self.assertRaises(ApplicationError):
            GlobalReferenceListCursorCodec(b"x" * 32).decode(
                token, session_token=b"s" * 32, page_size=25)


if __name__ == "__main__":
    unittest.main()
