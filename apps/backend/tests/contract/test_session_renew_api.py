from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import create_session_renew_router
from plm_assistant.modules.auth.application.session_service import (
    IssuedSession, SessionError, SessionPrincipal,
)
from plm_assistant.modules.auth.application.session_view import LoginSessionView


OLD_TOKEN, OLD_CSRF = b"o" * 32, b"c" * 32
NEW_TOKEN, NEW_CSRF = b"n" * 32, b"d" * 32


class FakeSessions:
    def __init__(self) -> None:
        self.user_id = uuid.uuid4()
        self.valid = True
        self.renew_calls = 0

    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> SessionPrincipal:
        if not self.valid or token != OLD_TOKEN:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != OLD_CSRF:
            raise SessionError("AUTH_ACCESS_DENIED")
        now = datetime.now(timezone.utc)
        return SessionPrincipal(uuid.uuid4(), self.user_id, 1,
                                now + timedelta(hours=8), now + timedelta(minutes=30))

    def renew(self, *, token: bytes, csrf_token: bytes, trace_id: uuid.UUID) -> IssuedSession:
        if not self.valid or token != OLD_TOKEN or csrf_token != OLD_CSRF:
            raise SessionError("AUTH_SESSION_EXPIRED")
        self.valid = False
        self.renew_calls += 1
        now = datetime.now(timezone.utc)
        return IssuedSession(uuid.uuid4(), self.user_id, NEW_TOKEN, NEW_CSRF,
                             now + timedelta(hours=8), now + timedelta(minutes=30))


class FakeViews:
    fail = False

    def resolve(self, user_id: uuid.UUID) -> LoginSessionView:
        if self.fail:
            raise RuntimeError("synthetic projection failure")
        return LoginSessionView(user_id, "Alice", "DEPLOYMENT_ADMIN", ())


class SessionRenewApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = FakeSessions()
        self.views = FakeViews()
        app = create_app(session_renew_router=create_session_renew_router(
            sessions=self.sessions, views=self.views,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        ))
        self.client = TestClient(app, base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test",
            "x-csrf-token": OLD_CSRF.hex(),
            "cookie": "plm_session=" + OLD_TOKEN.hex(),
        }

    def test_default_closed_and_atomic_http_rotation(self) -> None:
        with TestClient(create_app()) as bare:
            self.assertEqual(bare.post("/api/v1/auth/session:renew").status_code, 404)
        response = self.client.post("/api/v1/auth/session:renew", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["csrf_token"], NEW_CSRF.hex())
        self.assertIn("plm_session=" + NEW_TOKEN.hex(), response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertNotIn(NEW_TOKEN.hex(), response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.sessions.renew_calls, 1)
        self.assertEqual(self.client.post("/api/v1/auth/session:renew", headers=self.headers).status_code, 401)

    def test_csrf_origin_body_and_projection_failure_do_not_rotate(self) -> None:
        cases = (
            ({**self.headers, "origin": "https://evil.test"}, None, 403),
            ({k: v for k, v in self.headers.items() if k != "x-csrf-token"}, None, 403),
            ({**self.headers, "x-csrf-token": "bad"}, None, 403),
            (self.headers, {"ignored": True}, 400),
        )
        for headers, body, expected in cases:
            with self.subTest(expected=expected, headers=headers):
                response = self.client.post("/api/v1/auth/session:renew", headers=headers, json=body)
                self.assertEqual(response.status_code, expected)
        self.views.fail = True
        response = self.client.post("/api/v1/auth/session:renew", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.sessions.renew_calls, 0)
        self.views.fail = False
        self.assertEqual(self.client.post("/api/v1/auth/session:renew", headers=self.headers).status_code, 200)


if __name__ == "__main__":
    unittest.main()
