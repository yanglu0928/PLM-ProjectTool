from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import create_session_read_router
from plm_assistant.modules.auth.application.session_service import SessionError, SessionPrincipal
from plm_assistant.modules.auth.application.session_view import LoginSessionView


class FakeSessions:
    def __init__(self) -> None:
        self.user_id = uuid.uuid4()
        self.calls: list[bytes] = []
        self.fail = False

    def validate(self, token: bytes) -> SessionPrincipal:
        self.calls.append(token)
        if self.fail:
            raise SessionError("AUTH_SESSION_EXPIRED")
        now = datetime.now(timezone.utc)
        return SessionPrincipal(uuid.uuid4(), self.user_id, 1,
                                now + timedelta(hours=8), now + timedelta(minutes=30))


class FakeViews:
    def __init__(self, sessions: FakeSessions) -> None:
        self.sessions = sessions

    def resolve(self, user_id: uuid.UUID) -> LoginSessionView:
        return LoginSessionView(user_id, "Alice", "DEPLOYMENT_ADMIN", ())


class SessionReadApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = FakeSessions()
        self.app = create_app(session_router=create_session_read_router(
            sessions=self.sessions, views=FakeViews(self.sessions),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        ))
        self.client = TestClient(self.app, base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.cookie = "plm_session=" + "ab" * 32

    def test_default_closed_and_valid_read_has_no_csrf(self) -> None:
        with TestClient(create_app()) as bare:
            self.assertEqual(bare.get("/api/v1/auth/session").status_code, 404)
        response = self.client.get("/api/v1/auth/session", headers={"cookie": self.cookie})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["user"]["username_display"], "Alice")
        self.assertNotIn("csrf_token", response.text)
        self.assertNotIn("set-cookie", response.headers)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.sessions.calls, [bytes.fromhex("ab" * 32)])

    def test_missing_duplicate_malformed_or_revoked_cookie_denied(self) -> None:
        for cookie in (None, "plm_session=short", self.cookie + "; " + self.cookie,
                       "plm_session=" + "AB" * 32):
            with self.subTest(cookie=cookie):
                headers = {} if cookie is None else {"cookie": cookie}
                response = self.client.get("/api/v1/auth/session", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["error"]["code"], "AUTH_SESSION_EXPIRED")
        self.assertEqual(self.sessions.calls, [])
        self.sessions.fail = True
        response = self.client.get("/api/v1/auth/session", headers={"cookie": self.cookie})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)

    def test_untrusted_origin_rejected_before_cookie_lookup(self) -> None:
        response = self.client.get("/api/v1/auth/session", headers={
            "cookie": self.cookie, "origin": "https://evil.test",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.sessions.calls, [])


if __name__ == "__main__":
    unittest.main()
