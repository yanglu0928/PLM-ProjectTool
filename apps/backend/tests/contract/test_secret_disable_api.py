from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.api.secret_disable import create_secret_disable_router
from plm_assistant.modules.platform.application.secret_write import SecretWriteError


class Sessions:
    def __init__(self) -> None:
        self.fail = False

    def validate(self, token, *, csrf_token, require_csrf):
        if self.fail:
            raise SessionError("AUTH_SESSION_EXPIRED")
        assert require_csrf and len(token) == len(csrf_token) == 32
        return object()


class Writes:
    def __init__(self) -> None:
        self.calls = 0
        self.fail: str | None = None

    def disable(self, command):
        self.calls += 1
        assert command.expected_lock_version == 2
        if self.fail:
            raise SecretWriteError(self.fail)


class SecretDisableApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.writes = Sessions(), Writes()
        router = create_secret_disable_router(
            sessions=self.sessions, writes=self.writes,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(secret_disable_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/admin/secrets/{uuid.uuid4()}:disable"
        self.headers = {
            "origin": "https://plm.example.test", "cookie": "plm_session=" + "ab" * 32,
            "x-csrf-token": "cd" * 32, "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v2"',
        }

    def test_default_closed_and_disabled_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["state"], "DISABLED")
        self.assertIsNone(response.json()["data"]["current_version_no"])
        self.assertEqual(response.headers["etag"], '"v3"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.writes.calls, 1)

    def test_missing_or_weak_etag_and_nonempty_body_rejected(self) -> None:
        no_etag = {key: value for key, value in self.headers.items() if key != "if-match"}
        self.assertEqual(self.client.post(self.path, headers=no_etag).status_code, 428)
        self.assertEqual(self.client.post(self.path, headers={**self.headers,
                         "if-match": 'W/"v2"'}).status_code, 400)
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                         content=b"unexpected").status_code, 400)
        self.assertEqual(self.writes.calls, 0)

    def test_session_and_stale_version_fail_closed(self) -> None:
        self.sessions.fail = True
        self.assertEqual(self.client.post(self.path, headers=self.headers).status_code, 401)
        self.sessions.fail = False
        self.writes.fail = "CONFLICT_VERSION"
        response = self.client.post(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "CONFLICT_VERSION")


if __name__ == "__main__":
    unittest.main()
