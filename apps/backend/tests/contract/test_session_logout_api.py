from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import create_session_logout_router
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError


class FakeLogout:
    def __init__(self) -> None:
        self.calls = []
        self.error = None

    def logout(self, *, token, csrf_token, idempotency_key, trace_id):
        self.calls.append((token, csrf_token, idempotency_key, trace_id))
        if self.error is not None:
            raise self.error
        return True


class SessionLogoutApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = FakeLogout()
        app = create_app(session_logout_router=create_session_logout_router(
            sessions=self.sessions, origins=LoginOriginPolicy(["https://plm.example.test"]),
        ))
        self.client = TestClient(app, base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + "ab" * 32,
            "x-csrf-token": "cd" * 32,
            "idempotency-key": "synthetic-logout-key-1234",
        }

    def test_default_closed_and_success_clears_cookie(self) -> None:
        with TestClient(create_app()) as bare:
            self.assertEqual(bare.post("/api/v1/auth/logout").status_code, 404)
        response = self.client.post("/api/v1/auth/logout", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"revoked": True})
        self.assertEqual(response.headers["cache-control"], "no-store")
        cookie = response.headers["set-cookie"]
        for flag in ("plm_session=", "Max-Age=0", "HttpOnly", "Secure", "SameSite=lax"):
            self.assertIn(flag, cookie)
        self.assertEqual(len(self.sessions.calls), 1)
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers=self.headers).status_code, 200)

    def test_missing_key_csrf_origin_or_body_never_calls_service(self) -> None:
        cases = (
            ({k: v for k, v in self.headers.items() if k != "idempotency-key"}, None, 422),
            ({**self.headers, "idempotency-key": "short"}, None, 422),
            ({**self.headers, "x-csrf-token": "wrong"}, None, 403),
            ({**self.headers, "origin": "https://evil.test"}, None, 403),
            (self.headers, {"ignored": True}, 400),
        )
        for headers, body, expected in cases:
            with self.subTest(expected=expected, headers=headers):
                response = self.client.post("/api/v1/auth/logout", headers=headers, json=body)
                self.assertEqual(response.status_code, expected)
        self.assertEqual(self.sessions.calls, [])

    def test_conflict_and_expired_are_distinct_safe_errors(self) -> None:
        self.sessions.error = IdempotencyError("CONFLICT_IDEMPOTENCY")
        response = self.client.post("/api/v1/auth/logout", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("set-cookie", response.headers)
        self.sessions.error = SessionError("AUTH_SESSION_EXPIRED")
        response = self.client.post("/api/v1/auth/logout", headers=self.headers)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)


if __name__ == "__main__":
    unittest.main()
