from __future__ import annotations

import asyncio
import io
import threading
import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.api.download_version import create_document_download_router
from plm_assistant.modules.document.application.prepare_download import DownloadError, VerifiedDownload


class Sessions:
    def validate(self, token):
        if token != b"m" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Downloads:
    def __init__(self, version_id):
        self.version_id = version_id
        self.calls = 0
        self.fail = None
        self.stream = None
        self.mime = "application/pdf"
        self.entered = None
        self.release = None
        self.stream_factory = lambda: io.BytesIO(b"verified pdf bytes")

    def prepare(self, query, document_id, document_version_id):
        self.calls += 1
        if self.entered is not None:
            self.entered.set()
            self.release.wait(timeout=5)
        if self.fail:
            raise DownloadError(self.fail)
        assert document_version_id == self.version_id
        self.stream = self.stream_factory()
        return VerifiedDownload(document_version_id, len(b"verified pdf bytes"),
                                self.mime, b"h" * 32, self.stream)


class DocumentDownloadApiTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.downloads = Downloads(self.version_id)
        router = create_document_download_router(
            sessions=Sessions(), downloads=self.downloads,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            max_inflight=1,
        )
        self.app = create_app(document_download_router=router)
        self.client = TestClient(self.app, base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.project_id}/documents/{self.document_id}"
                     f"/versions/{self.version_id}/content")
        self.global_path = (f"/api/v1/global/documents/{self.document_id}"
                            f"/versions/{self.version_id}/content")
        self.cookie = "plm_session=" + (b"m" * 32).hex()

    def get(self, path, *, headers=None):
        return self.client.get(path, headers={"cookie": self.cookie, **(headers or {})})

    def test_default_closed_and_verified_stream_headers_and_cleanup(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        response = self.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"verified pdf bytes")
        self.assertEqual(response.headers["content-length"], str(len(response.content)))
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("storage", response.headers["content-disposition"])
        self.assertTrue(self.downloads.stream.closed)
        self.assertEqual(self.get(self.global_path).status_code, 200)

    def test_bad_query_range_and_integrity_fail_before_stream(self):
        for path, headers in (
            (self.path + "?x=1", None),
            (self.path, {"range": "bytes=0-10"}),
            (self.path, {"if-range": '"old"'}),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, headers=headers).status_code, 400)
        self.assertEqual(self.downloads.calls, 0)
        self.downloads.fail = "FILE_INTEGRITY_MISMATCH"
        self.assertEqual(self.get(self.path).status_code, 409)
        self.assertIsNone(self.downloads.stream)

    def test_malformed_mime_closes_snapshot(self):
        self.downloads.mime = "application/pdf\r\nX-Leak: yes"
        self.assertEqual(self.get(self.path).status_code, 503)
        self.assertTrue(self.downloads.stream.closed)

    def test_bounded_parallel_downloads_release_slot(self):
        self.downloads.entered = threading.Event()
        self.downloads.release = threading.Event()
        result = []

        def first_request():
            with TestClient(self.app, base_url="https://plm.example.test") as client:
                result.append(client.get(self.path, headers={"cookie": self.cookie}).status_code)

        worker = threading.Thread(target=first_request)
        worker.start()
        try:
            self.assertTrue(self.downloads.entered.wait(timeout=5))
            self.assertEqual(self.get(self.path).status_code, 503)
        finally:
            self.downloads.release.set()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [200])
        self.assertEqual(self.get(self.path).status_code, 200)

    def test_stream_failure_closes_snapshot_and_releases_slot(self):
        class FailingStream(io.BytesIO):
            def __init__(self):
                super().__init__(b"verified pdf bytes")
                self.reads = 0

            def read(self, size=-1):
                self.reads += 1
                if self.reads > 1:
                    raise OSError("synthetic stream failure")
                return super().read(size)

        self.downloads.stream_factory = FailingStream
        with self.assertRaises(Exception):
            self.get(self.path)
        self.assertTrue(self.downloads.stream.closed)
        self.downloads.stream_factory = lambda: io.BytesIO(b"verified pdf bytes")
        self.assertEqual(self.get(self.path).status_code, 200)

    def test_client_send_disconnect_closes_snapshot_and_releases_slot(self):
        async def disconnected_send(message):
            if message["type"] == "http.response.body" and message.get("body"):
                raise OSError("synthetic client disconnected")

        async def request():
            seen = False

            async def receive():
                nonlocal seen
                if not seen:
                    seen = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                await asyncio.Event().wait()

            scope = {
                "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                "http_version": "1.1", "method": "GET", "scheme": "https",
                "path": self.path, "raw_path": self.path.encode("ascii"),
                "query_string": b"", "root_path": "",
                "headers": [(b"host", b"plm.example.test"),
                            (b"cookie", self.cookie.encode("ascii"))],
                "client": ("127.0.0.1", 12345),
                "server": ("plm.example.test", 443),
            }
            await self.app(scope, receive, disconnected_send)

        with self.assertRaises(Exception):
            asyncio.run(asyncio.wait_for(request(), timeout=3))
        self.assertEqual(self.downloads.calls, 1)
        self.assertTrue(self.downloads.stream.closed)
        self.assertEqual(self.get(self.path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
