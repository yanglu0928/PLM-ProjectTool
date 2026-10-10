from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.read_documents import create_document_read_router
from plm_assistant.modules.document.application.read_documents import (
    DocumentPage, DocumentReadError, DocumentView,
)


class Sessions:
    def validate(self, token):
        if token not in (b"m" * 32, b"o" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Documents:
    def __init__(self, project_id):
        self.project_id = project_id
        self.ids = tuple(sorted(uuid.uuid4() for _ in range(3)))
        self.calls = 0
        self.fail = None

    def _view(self, document_id, scope, project_id):
        return DocumentView(
            document_id, scope, project_id, "CONTRACT", None, "Title", "Display.pdf",
            "ACTIVE", uuid.uuid4(), None, datetime(2026, 9, 26, tzinfo=timezone.utc),
            '"v0"',
        )

    def list(self, query, *, after_document_id=None, limit=50):
        self.calls += 1
        if self.fail:
            raise DocumentReadError(self.fail)
        if query.scope == "PROJECT" and query.project_id != self.project_id:
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        offset = 0 if after_document_id is None else self.ids.index(after_document_id) + 1
        selection = self.ids[offset:offset + limit]
        items = tuple(self._view(item, query.scope, query.project_id) for item in selection)
        more = offset + limit < len(self.ids)
        return DocumentPage(items, items[-1].document_id if more else None, more)

    def get(self, query, document_id):
        self.calls += 1
        if self.fail:
            raise DocumentReadError(self.fail)
        if (query.scope == "PROJECT" and query.project_id != self.project_id
                or document_id not in self.ids):
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        return self._view(document_id, query.scope, query.project_id)


class DocumentReadApiTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.documents = Documents(self.project_id)
        router = create_document_read_router(
            sessions=Sessions(), documents=self.documents,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=DocumentListCursorCodec(b"k" * 32),
        )
        self.client = TestClient(create_app(document_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.project_path = f"/api/v1/projects/{self.project_id}/documents"
        self.global_path = "/api/v1/global/documents"
        self.cookie = "plm_session=" + (b"m" * 32).hex()

    def get(self, path, *, cookie=None):
        return self.client.get(path, headers={"cookie": cookie or self.cookie})

    def test_opt_in_pages_and_safe_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.project_path).status_code, 404)
        first = self.get(self.project_path + "?page_size=2")
        self.assertEqual(first.status_code, 200)
        data = first.json()["data"]
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(data["has_more"])
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(set(data["items"][0]), {
            "document_id", "scope", "category", "subtype", "title", "display_name",
            "state", "latest_version_ref", "effective_version_ref", "created_at", "etag",
        })
        second = self.get(self.project_path + "?page_size=2&cursor=" + data["next_cursor"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()["data"]["items"]), 1)
        self.assertIsNone(second.json()["data"]["next_cursor"])

    def test_global_and_detail(self):
        self.assertEqual(self.get(self.global_path).status_code, 200)
        detail = self.get(self.project_path + "/" + str(self.documents.ids[0]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.headers["etag"], '"v0"')
        self.assertEqual(self.get(self.project_path + "/" + str(uuid.uuid4())).status_code, 404)

    def test_cursor_scope_context_and_query_fail_before_read(self):
        cursor = self.get(self.project_path + "?page_size=2").json()["data"]["next_cursor"]
        count = self.documents.calls
        tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        for path, cookie in (
            (self.project_path + "?page_size=2&cursor=" + tampered, None),
            (self.project_path + "?page_size=3&cursor=" + cursor, None),
            (self.project_path + "?page_size=2&cursor=" + cursor,
             "plm_session=" + (b"o" * 32).hex()),
            (self.global_path + "?page_size=2&cursor=" + cursor, None),
            (f"/api/v1/projects/{uuid.uuid4()}/documents?page_size=2&cursor=" + cursor, None),
            (self.project_path + "?page_size=2&page_size=3", None),
            (self.project_path + "?order_by=document_id", None),
            (self.project_path + "/" + str(self.documents.ids[0]) + "?x=1", None),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, cookie=cookie).status_code, 400)
        self.assertEqual(self.documents.calls, count)

    def test_read_failures_and_scope_hiding(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("DOCUMENT_UNAVAILABLE", 503)):
            self.documents.fail = code
            with self.subTest(code=code):
                self.assertEqual(self.get(self.project_path).status_code, expected)
        self.documents.fail = None
        self.assertEqual(self.get(f"/api/v1/projects/{uuid.uuid4()}/documents").status_code, 404)
        self.assertEqual(self.get(self.project_path + "/" + str(uuid.UUID(int=0))).status_code, 404)


if __name__ == "__main__":
    unittest.main()
