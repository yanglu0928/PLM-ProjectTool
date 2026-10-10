from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.api.read_versions import create_document_version_read_router
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentVersionPage, DocumentVersionView,
)


class Sessions:
    def validate(self, token):
        if token not in (b"m" * 32, b"o" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Documents:
    def __init__(self, document_id, project_id):
        self.document_id = document_id
        self.project_id = project_id
        self.ids = tuple(uuid.uuid4() for _ in range(3))
        self.calls = 0
        self.fail = None

    def view(self, no):
        return DocumentVersionView(
            self.ids[no - 1], self.document_id, no, "a" * 64, 7,
            "application/pdf", "AVAILABLE", self.ids[no - 2] if no > 1 else None,
            datetime(2026, 9, 26, tzinfo=timezone.utc), None,
        )

    def list_versions(self, query, document_id, *, before_version_no=None, limit=50):
        self.calls += 1
        if self.fail:
            raise DocumentReadError(self.fail)
        if document_id != self.document_id or (query.scope == "PROJECT"
                                               and query.project_id != self.project_id):
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        numbers = [no for no in (3, 2, 1)
                   if before_version_no is None or no < before_version_no]
        selected = numbers[:limit]
        more = len(numbers) > limit
        return DocumentVersionPage(tuple(self.view(no) for no in selected),
                                   selected[-1] if more else None, more)

    def get_version(self, query, document_id, version_id):
        self.calls += 1
        if self.fail:
            raise DocumentReadError(self.fail)
        if (document_id != self.document_id or version_id not in self.ids
                or query.scope == "PROJECT" and query.project_id != self.project_id):
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        return self.view(self.ids.index(version_id) + 1)


class DocumentVersionReadApiTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.documents = Documents(self.document_id, self.project_id)
        router = create_document_version_read_router(
            sessions=Sessions(), documents=self.documents,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=VersionListCursorCodec(b"v" * 32),
        )
        self.client = TestClient(create_app(document_version_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project_id}/documents/{self.document_id}/versions"
        self.global_path = f"/api/v1/global/documents/{self.document_id}/versions"
        self.cookie = "plm_session=" + (b"m" * 32).hex()

    def get(self, path, *, cookie=None):
        return self.client.get(path, headers={"cookie": cookie or self.cookie})

    def test_opt_in_two_pages_and_safe_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        first = self.get(self.path + "?page_size=2")
        self.assertEqual(first.status_code, 200)
        data = first.json()["data"]
        self.assertEqual([v["version_no"] for v in data["items"]], [3, 2])
        self.assertTrue(data["has_more"])
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(set(data["items"][0]), {
            "document_version_id", "version_no", "content_sha256", "size_bytes",
            "detected_mime", "availability_state", "supersedes_version_ref",
            "created_at", "integrity_checked_at",
        })
        second = self.get(self.path + "?page_size=2&cursor=" + data["next_cursor"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual([v["version_no"] for v in second.json()["data"]["items"]], [1])
        self.assertIsNone(second.json()["data"]["next_cursor"])

    def test_detail_global_and_errors(self):
        version_id = self.documents.ids[0]
        self.assertEqual(self.get(self.path + "/" + str(version_id)).json()["data"]["version_no"], 1)
        self.assertEqual(self.get(self.global_path).status_code, 200)
        self.assertEqual(self.get(self.path + "/" + str(uuid.uuid4())).status_code, 404)
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("DOCUMENT_UNAVAILABLE", 503)):
            self.documents.fail = code
            with self.subTest(code=code):
                self.assertEqual(self.get(self.path).status_code, expected)

    def test_cursor_context_and_query_fail_before_read(self):
        cursor = self.get(self.path + "?page_size=2").json()["data"]["next_cursor"]
        count = self.documents.calls
        tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        for path, cookie in (
            (self.path + "?page_size=2&cursor=" + tampered, None),
            (self.path + "?page_size=3&cursor=" + cursor, None),
            (self.path + "?page_size=2&cursor=" + cursor,
             "plm_session=" + (b"o" * 32).hex()),
            (self.global_path + "?page_size=2&cursor=" + cursor, None),
            (f"/api/v1/projects/{self.project_id}/documents/{uuid.uuid4()}/versions?page_size=2&cursor=" + cursor, None),
            (f"/api/v1/projects/{uuid.uuid4()}/documents/{self.document_id}/versions?page_size=2&cursor=" + cursor, None),
            (self.path + "?page_size=2&page_size=3", None),
            (self.path + "?order_by=version_no", None),
            (self.path + "/" + str(self.documents.ids[0]) + "?x=1", None),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, cookie=cookie).status_code, 400)
        self.assertEqual(self.documents.calls, count)


if __name__ == "__main__":
    unittest.main()
