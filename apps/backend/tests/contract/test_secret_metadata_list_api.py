from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.api.secret_metadata import create_secret_metadata_list_router
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.secret_metadata import SecretMetadataError, SecretMetadataView


class Sessions:
    def validate(self, token: bytes) -> object:
        return object()


class Metadata:
    def __init__(self) -> None:
        now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        self.rows = [SecretMetadataView(uuid.uuid4(), "AI_PROVIDER_KEY", "ACTIVE",
                                        "AI_PROVIDER_ADAPTER", 1, now - timedelta(i), now, 1)
                     for i in range(3)]
        self.fail: str | None = None
        self.calls = 0

    def list_http_page(self, query, *, after, limit):
        self.calls += 1
        if self.fail:
            raise SecretMetadataError(self.fail)
        rows = self.rows
        if after is not None:
            rows = [row for row in rows if (row.created_at, row.secret_id) < after]
        return rows[:limit]


class SecretMetadataListApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = Metadata()
        self.codec = SecretListCursorCodec(b"c" * 32)
        router = create_secret_metadata_list_router(
            sessions=Sessions(), metadata=self.metadata,
            origins=LoginOriginPolicy(["https://plm.example.test"]), cursors=self.codec,
        )
        self.client = TestClient(create_app(secret_metadata_list_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.cookie = "plm_session=" + "ab" * 32

    def get(self, path="/api/v1/admin/secrets", *, cookie=None):
        return self.client.get(path, headers={"cookie": cookie or self.cookie})

    def test_two_pages_and_safe_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.get("/api/v1/admin/secrets").status_code, 404)
        first = self.get("/api/v1/admin/secrets?page_size=2")
        self.assertEqual(first.status_code, 200)
        data = first.json()["data"]
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(data["has_more"])
        self.assertNotIn("ciphertext", first.text)
        self.assertNotIn("secret_value", first.text)
        self.assertEqual(first.headers["cache-control"], "no-store")
        second = self.get(f"/api/v1/admin/secrets?page_size=2&cursor={data['next_cursor']}")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()["data"]["items"]), 1)
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertIsNone(second.json()["data"]["next_cursor"])
        seen = [row["secret_id"] for row in data["items"] + second.json()["data"]["items"]]
        self.assertEqual(len(set(seen)), 3)

    def test_invalid_cursor_scope_and_query_fail_before_data_read(self) -> None:
        first = self.get("/api/v1/admin/secrets?page_size=1").json()["data"]["next_cursor"]
        count = self.metadata.calls
        for path, cookie in (
            (f"/api/v1/admin/secrets?page_size=1&cursor={first[:-1]}{'A' if first[-1] != 'A' else 'B'}", None),
            (f"/api/v1/admin/secrets?page_size=2&cursor={first}", None),
            (f"/api/v1/admin/secrets?page_size=1&cursor={first}", "plm_session=" + "cd" * 32),
            ("/api/v1/admin/secrets?page_size=1&page_size=2", None),
            ("/api/v1/admin/secrets?order_by=secret_id", None),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, cookie=cookie).status_code, 400)
        self.assertEqual(self.metadata.calls, count)

    def test_bounds_and_fail_closed(self) -> None:
        for value in ("0", "201", "01", "bad"):
            self.assertEqual(self.get(f"/api/v1/admin/secrets?page_size={value}").status_code, 422)
        self.metadata.fail = "AUTH_ACCESS_DENIED"
        self.assertEqual(self.get().status_code, 404)
        self.metadata.fail = "SECRET_UNAVAILABLE"
        self.assertEqual(self.get().status_code, 503)

    def test_cursor_key_required(self) -> None:
        with self.assertRaises(ValueError):
            SecretListCursorCodec(b"short")
        with self.assertRaises(ApplicationError) as caught:
            self.codec.decode("not-a-cursor", session_token=b"a" * 32, page_size=50)
        self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")


if __name__ == "__main__":
    unittest.main()
