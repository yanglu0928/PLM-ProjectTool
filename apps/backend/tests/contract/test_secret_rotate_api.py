from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.api.secret_rotate import create_secret_rotate_router
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
        self.values: list[bytearray] = []

    def rotate(self, command):
        self.calls += 1
        self.values.append(command.secret_value)
        assert command.expected_lock_version == 3
        if self.fail:
            raise SecretWriteError(self.fail)
        return 2


class SecretRotateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.writes = Sessions(), Writes()
        router = create_secret_rotate_router(
            sessions=self.sessions, writes=self.writes,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(secret_rotate_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/admin/secrets/{uuid.uuid4()}:rotate"
        self.headers = {
            "origin": "https://plm.example.test", "cookie": "plm_session=" + "ab" * 32,
            "x-csrf-token": "cd" * 32, "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v3"',
        }
        self.body = {"secret_value": "synthetic-rotated-value"}

    def test_default_closed_and_metadata_only_response(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["current_version_no"], 2)
        self.assertEqual(response.headers["etag"], '"v4"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn(self.body["secret_value"], response.text)
        self.assertEqual(self.writes.values[0], bytearray(len(self.body["secret_value"])))

    def test_missing_weak_or_duplicate_etag_does_not_rotate(self) -> None:
        headers = {key: value for key, value in self.headers.items() if key != "if-match"}
        response = self.client.post(self.path, headers=headers, json=self.body)
        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.json()["error"]["code"], "CONFLICT_VERSION_REQUIRED")
        for value in ('W/"v3"', '"v3", "v4"', "*"):
            with self.subTest(value=value):
                self.assertEqual(self.client.post(
                    self.path, headers={**self.headers, "if-match": value}, json=self.body,
                ).status_code, 400)
        self.assertEqual(self.writes.calls, 0)

    def test_auth_body_and_stale_version_fail_closed(self) -> None:
        self.sessions.fail = True
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          json=self.body).status_code, 401)
        self.sessions.fail = False
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          json={"secret_value": ""}).status_code, 422)
        self.assertEqual(self.writes.calls, 0)
        self.writes.fail = "CONFLICT_VERSION"
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "CONFLICT_VERSION")
        self.assertNotIn(self.body["secret_value"], response.text)
        self.assertEqual(self.writes.values[-1], bytearray(len(self.body["secret_value"])))


if __name__ == "__main__":
    unittest.main()
