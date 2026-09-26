from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.api.secret_create import create_secret_create_router
from plm_assistant.modules.platform.application.secret_access import SecretRef
from plm_assistant.modules.platform.application.secret_write import SecretWriteError


class Sessions:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def validate(self, token, *, csrf_token, require_csrf):
        self.calls += 1
        if self.fail:
            raise SessionError("AUTH_SESSION_EXPIRED")
        assert require_csrf and len(token) == len(csrf_token) == 32
        return object()


class Writes:
    def __init__(self) -> None:
        self.calls = 0
        self.fail: str | None = None
        self.ref = SecretRef(uuid.uuid4())
        self.values: list[bytearray] = []

    def create(self, command):
        self.calls += 1
        self.values.append(command.secret_value)
        if self.fail:
            raise SecretWriteError(self.fail)
        return self.ref


class SecretCreateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.writes = Sessions(), Writes()
        router = create_secret_create_router(
            sessions=self.sessions, writes=self.writes,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(secret_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + "ab" * 32,
            "x-csrf-token": "cd" * 32,
            "idempotency-key": str(uuid.uuid4()),
        }
        self.body = {
            "purpose": "AI_PROVIDER_KEY",
            "allowed_consumer": "AI_PROVIDER_ADAPTER",
            "secret_value": "synthetic-do-not-echo",
        }

    def test_default_closed_and_write_only_201(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post("/api/v1/admin/secrets").status_code, 404)
        response = self.client.post("/api/v1/admin/secrets", headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"], {"secret_id": str(self.writes.ref.secret_id)})
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.headers["location"],
                         f"/api/v1/admin/secrets/{self.writes.ref.secret_id}")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("synthetic-do-not-echo", response.text)
        self.assertNotIn("set-cookie", response.headers)
        self.assertEqual(self.writes.values[0], bytearray(len(b"synthetic-do-not-echo")))

    def test_credentials_and_origin_gate_before_body(self) -> None:
        for field, value, status in (
            ("origin", "https://evil.test", 403),
            ("cookie", "plm_session=short", 401),
            ("x-csrf-token", "bad", 403),
            ("idempotency-key", "short", 422),
        ):
            with self.subTest(field=field):
                headers = {**self.headers, field: value}
                self.assertEqual(self.client.post(
                    "/api/v1/admin/secrets", headers=headers, json=self.body,
                ).status_code, status)
        self.assertEqual(self.writes.calls, 0)
        self.sessions.fail = True
        self.assertEqual(self.client.post(
            "/api/v1/admin/secrets", headers=self.headers, json=self.body,
        ).status_code, 401)
        self.assertEqual(self.writes.calls, 0)

    def test_strict_body_and_enum_reject_before_write(self) -> None:
        cases = (
            (b'{"purpose":"AI_PROVIDER_KEY","purpose":"AI_PROVIDER_KEY"}', 400),
            (b'{"purpose":"AI_PROVIDER_KEY","allowed_consumer":"AI_PROVIDER_ADAPTER",'
             b'"secret_value":"x","extra":1}', 400),
            (b'{"purpose":"AI_PROVIDER_KEY","allowed_consumer":"AI_PROVIDER_ADAPTER",'
             b'"secret_value":NaN}', 400),
            (b'{"purpose":"BAD","allowed_consumer":"AI_PROVIDER_ADAPTER",'
             b'"secret_value":"x"}', 422),
            (b'{"purpose":"AI_PROVIDER_KEY","allowed_consumer":"AI_PROVIDER_ADAPTER",'
             b'"secret_value":""}', 422),
            (b"x" * 70_001, 400),
        )
        for body, status in cases:
            with self.subTest(body=body[:40]):
                response = self.client.post(
                    "/api/v1/admin/secrets", headers={**self.headers,
                    "content-type": "application/json"}, content=body,
                )
                self.assertEqual(response.status_code, status)
                self.assertNotIn("secret_value", response.text)
        self.assertEqual(self.writes.calls, 0)

    def test_write_failure_is_safe_and_erases_value(self) -> None:
        for failure, status in (("AUTH_ACCESS_DENIED", 404),
                                ("CONFLICT_IDEMPOTENCY", 409),
                                ("PLATFORM_SECRET_UNAVAILABLE", 503)):
            with self.subTest(failure=failure):
                self.writes.fail = failure
                response = self.client.post(
                    "/api/v1/admin/secrets", headers=self.headers, json=self.body,
                )
                self.assertEqual(response.status_code, status)
                self.assertNotIn(self.body["secret_value"], response.text)
                self.assertEqual(self.writes.values[-1],
                                 bytearray(len(self.body["secret_value"])))


if __name__ == "__main__":
    unittest.main()
