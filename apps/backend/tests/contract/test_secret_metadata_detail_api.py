from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.api.secret_metadata import create_secret_metadata_detail_router
from plm_assistant.modules.platform.application.secret_metadata import (
    SecretMetadataError, SecretMetadataView,
)


class FakeSessions:
    def __init__(self) -> None:
        self.calls = 0
        self.valid = True

    def validate(self, token: bytes) -> object:
        self.calls += 1
        if not self.valid:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class FakeMetadata:
    def __init__(self) -> None:
        self.calls = 0
        self.failure: str | None = None
        now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        self.view = SecretMetadataView(uuid.uuid4(), "AI_PROVIDER_KEY", "ACTIVE",
                                       "AI_PROVIDER_ADAPTER", 2, now, now, 7)

    def get(self, query, secret_id):
        self.calls += 1
        if self.failure:
            raise SecretMetadataError(self.failure)
        if secret_id != self.view.secret_id:
            raise SecretMetadataError("SECRET_NOT_FOUND")
        return self.view


class SecretMetadataDetailApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.metadata = FakeSessions(), FakeMetadata()
        router = create_secret_metadata_detail_router(
            sessions=self.sessions, metadata=self.metadata,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(secret_metadata_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/admin/secrets/{self.metadata.view.secret_id}"
        self.cookie = "plm_session=" + "ab" * 32

    def test_explicit_mount_safe_projection_and_strong_etag(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.get(self.path).status_code, 404)
        response = self.client.get(self.path, headers={"cookie": self.cookie})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v7"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(set(response.json()["data"]), {
            "secret_id", "purpose", "state", "allowed_consumer", "current_version_no",
            "created_at", "updated_at",
        })
        self.assertNotIn("ciphertext", response.text)
        self.assertNotIn("secret_value", response.text)
        self.assertNotIn("set-cookie", response.headers)

    def test_host_cookie_and_session_gate_before_metadata(self) -> None:
        for headers, expected in (
            ({}, 401), ({"cookie": "plm_session=short"}, 401),
            ({"cookie": self.cookie, "origin": "https://evil.test"}, 403),
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get(self.path, headers=headers).status_code, expected)
        self.assertEqual(self.metadata.calls, 0)
        self.sessions.valid = False
        self.assertEqual(self.client.get(self.path, headers={"cookie": self.cookie}).status_code, 401)
        self.assertEqual(self.metadata.calls, 0)

    def test_permission_missing_and_guard_failure_are_closed(self) -> None:
        for failure, status in (("AUTH_ACCESS_DENIED", 404), ("SECRET_NOT_FOUND", 404),
                                ("SECRET_UNAVAILABLE", 503)):
            with self.subTest(failure=failure):
                self.metadata.failure = failure
                response = self.client.get(self.path, headers={"cookie": self.cookie})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("etag", response.headers)


if __name__ == "__main__":
    unittest.main()
