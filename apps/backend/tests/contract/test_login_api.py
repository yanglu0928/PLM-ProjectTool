from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login import create_login_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.login_service import LoginError
from plm_assistant.modules.auth.application.session_service import IssuedSession


class FakeLogin:
    def __init__(self) -> None:
        self.calls = []
        self.error = None

    def login(self, attempt):
        self.calls.append((attempt.username, attempt.client_ip, attempt.trace_id))
        if self.error:
            raise LoginError(self.error)
        now = datetime.now(timezone.utc)
        return IssuedSession(uuid.uuid4(), uuid.uuid4(), b"t" * 32, b"c" * 32,
                             now + timedelta(hours=8), now + timedelta(minutes=30))


class LoginApiTests(unittest.TestCase):
    def setUp(self):
        self.login = FakeLogin()
        self.origins = LoginOriginPolicy(["https://plm.example.test", "http://localhost"])
        self.app = create_app(login_router=create_login_router(login=self.login, origins=self.origins))
        self.client = TestClient(self.app, base_url="https://plm.example.test")
        self.headers = {"origin": "https://plm.example.test"}

    def tearDown(self):
        self.client.close()

    def test_opt_in_and_secure_cookie_response(self):
        with TestClient(create_app()) as bare:
            self.assertEqual(bare.post("/api/v1/auth/login").status_code, 404)
        response = self.client.post("/api/v1/auth/login", headers=self.headers,
                                    json={"username": "alice", "password": "some-password"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trace_id"], response.headers["x-trace-id"])
        self.assertEqual(response.json()["data"]["csrf_token"], (b"c" * 32).hex())
        self.assertNotIn("some-password", str(response.json()))
        self.assertNotIn((b"t" * 32).hex(), str(response.json()))
        cookie = response.headers["set-cookie"]
        for flag in ("plm_session=", "HttpOnly", "Secure", "SameSite=lax", "Path=/"):
            self.assertIn(flag, cookie)
        self.assertEqual(len(self.login.calls), 1)

    def test_insecure_cookie_only_for_trusted_loopback(self):
        with TestClient(self.app, base_url="http://localhost") as client:
            response = client.post("/api/v1/auth/login", headers={"origin": "http://localhost"},
                                   json={"username": "alice", "password": "password"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Secure", response.headers["set-cookie"])

    def test_untrusted_origin_and_bad_body_never_call_service(self):
        for headers, data in (({}, {"username": "a", "password": "b"}),
                              ({"origin": "https://evil.test"}, {"username": "a", "password": "b"}),
                              (self.headers, {"username": "a", "password": "b", "extra": 1})):
            response = self.client.post("/api/v1/auth/login", headers=headers, json=data)
            self.assertIn(response.status_code, (400, 403))
            self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.login.calls, [])
        too_large = self.client.post("/api/v1/auth/login", content=b"x" * 4097,
                                     headers={**self.headers, "content-type": "application/json"},
                                     )
        self.assertEqual(too_large.status_code, 400)

    def test_fixed_credential_error_without_cookie(self):
        self.login.error = "AUTH_INVALID_CREDENTIALS"
        response = self.client.post("/api/v1/auth/login", headers=self.headers,
                                    json={"username": "missing", "password": "private"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTH_INVALID_CREDENTIALS")
        self.assertNotIn("set-cookie", response.headers)
        self.assertNotIn("missing", response.text)
        self.assertNotIn("private", response.text)


if __name__ == "__main__":
    unittest.main()
