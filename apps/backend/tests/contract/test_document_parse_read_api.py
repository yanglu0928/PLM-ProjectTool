from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.read_parses import create_document_parse_read_router
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, ParseRecordPage, ParseRecordView,
)


class Sessions:
    def validate(self, token):
        if token not in (b"m" * 32, b"o" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Documents:
    def __init__(self, document_id, version_id, project_id):
        self.document_id, self.version_id, self.project_id = (
            document_id, version_id, project_id,
        )
        self.ids = sorted((uuid.uuid4() for _ in range(3)), reverse=True)
        self.calls = 0
        self.fail = None

    def list_parses(self, query, document_id, version_id, *, before=None, limit=50):
        self.calls += 1
        if self.fail:
            raise DocumentReadError(self.fail)
        if (document_id != self.document_id or version_id != self.version_id
                or query.scope == "PROJECT" and query.project_id != self.project_id):
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        stamp = datetime(2026, 9, 26, tzinfo=timezone.utc)
        remaining = [record_id for record_id in self.ids
                     if before is None or (stamp, record_id) < before]
        selected = remaining[:limit]
        items = tuple(ParseRecordView(record_id, version_id, "PDF", "1.0",
                                      "PENDING", no + 1, uuid.uuid4(), None,
                                      None, None, stamp, None, None)
                      for no, record_id in enumerate(selected))
        more = len(remaining) > limit
        return ParseRecordPage(items, (stamp, selected[-1]) if more else None, more)


class DocumentParseReadApiTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.documents = Documents(self.document_id, self.version_id, self.project_id)
        router = create_document_parse_read_router(
            sessions=Sessions(), documents=self.documents,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=ParseListCursorCodec(b"p" * 32),
        )
        self.client = TestClient(create_app(document_parse_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.project_id}/documents/"
                     f"{self.document_id}/versions/{self.version_id}/parses")
        self.global_path = (f"/api/v1/global/documents/{self.document_id}/"
                            f"versions/{self.version_id}/parses")
        self.cookie = "plm_session=" + (b"m" * 32).hex()

    def get(self, path, *, cookie=None):
        return self.client.get(path, headers={"cookie": cookie or self.cookie})

    def test_opt_in_pages_and_safe_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        first = self.get(self.path + "?page_size=2")
        self.assertEqual(first.status_code, 200)
        data = first.json()["data"]
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(data["has_more"])
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(set(data["items"][0]), {
            "parse_record_id", "parser_profile", "parser_version", "parse_state",
            "attempt_no", "job_ref", "result_ref", "error_code", "retryable",
            "created_at", "started_at", "completed_at",
        })
        second = self.get(self.path + "?page_size=2&cursor=" + data["next_cursor"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()["data"]["items"]), 1)
        self.assertIsNone(second.json()["data"]["next_cursor"])
        self.assertEqual(self.get(self.global_path).status_code, 200)

    def test_cursor_context_and_errors(self):
        cursor = self.get(self.path + "?page_size=2").json()["data"]["next_cursor"]
        calls = self.documents.calls
        tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        for path, cookie in (
            (self.path + "?page_size=2&cursor=" + tampered, None),
            (self.path + "?page_size=3&cursor=" + cursor, None),
            (self.path + "?page_size=2&cursor=" + cursor,
             "plm_session=" + (b"o" * 32).hex()),
            (self.global_path + "?page_size=2&cursor=" + cursor, None),
            (f"/api/v1/projects/{uuid.uuid4()}/documents/{self.document_id}/"
             f"versions/{self.version_id}/parses?page_size=2&cursor={cursor}", None),
            (f"/api/v1/projects/{self.project_id}/documents/{self.document_id}/"
             f"versions/{uuid.uuid4()}/parses?page_size=2&cursor={cursor}", None),
            (self.path + "?page_size=2&page_size=3", None),
            (self.path + "?order_by=created_at", None),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, cookie=cookie).status_code, 400)
        self.assertEqual(self.documents.calls, calls)
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("DOCUMENT_UNAVAILABLE", 503)):
            self.documents.fail = code
            with self.subTest(code=code):
                self.assertEqual(self.get(self.path).status_code, expected)


if __name__ == "__main__":
    unittest.main()
