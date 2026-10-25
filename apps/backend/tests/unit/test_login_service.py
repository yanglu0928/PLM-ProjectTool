from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimitError
from plm_assistant.modules.auth.application.login_service import LoginAttempt, LoginError, LoginService
from plm_assistant.modules.auth.application.session_service import IssuedSession, SessionError


NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


class Tx:
    def __init__(self, deps):
        self.deps = deps

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.deps.commits += 1


class Deps:
    def __init__(self):
        self.actor = uuid.uuid4()
        self.rate_error = None
        self.session_error = None
        self.audit_error = False
        self.rate_unexpected = False
        self.identity_error = False
        self.dummy_error = False
        self.calls = []
        self.commits = 0

    def uow(self):
        return Tx(self)

    def require_slot(self, **_):
        self.calls.append("rate")
        if self.rate_unexpected:
            raise RuntimeError("synthetic rate database error")
        if self.rate_error:
            raise LoginRateLimitError(self.rate_error)

    def find_active(self, tx, normalized_username):
        self.calls.append("identity")
        if self.identity_error:
            raise RuntimeError("synthetic identity database error")
        return self.actor if normalized_username == "alice" else None

    def consume(self, password):
        self.calls.append("dummy")
        if self.dummy_error:
            raise RuntimeError("synthetic scrypt unavailable")

    def issue(self, **kwargs):
        self.calls.append("issue")
        if self.session_error:
            if self.session_error == "RUNTIME":
                raise RuntimeError("synthetic session database error")
            raise SessionError(self.session_error)
        return IssuedSession(uuid.uuid4(), kwargs["user_id"], b"s" * 32,
                             b"c" * 32, NOW + timedelta(hours=8), NOW + timedelta(minutes=30))

    def append(self, tx, event):
        self.calls.append("audit")
        if self.audit_error:
            raise RuntimeError("synthetic audit failure")
        self.last_event = event
        return uuid.uuid4()


class LoginServiceTests(unittest.TestCase):
    def setUp(self):
        self.deps = Deps()
        self.service = LoginService(
            unit_of_work=self.deps.uow, rate=self.deps,
            identity=self.deps, missing_verifier=self.deps,
            sessions=self.deps, audit=self.deps,
        )

    def attempt(self, username="Alice"):
        return LoginAttempt(username, bytearray(b"synthetic-pass"), "127.0.0.1", uuid.uuid4())

    def test_success_uses_normalized_identity_and_clears_password(self):
        attempt = self.attempt(" ALICE ")
        session = self.service.login(attempt)
        self.assertEqual(session.user_id, self.deps.actor)
        self.assertEqual(self.deps.calls, ["rate", "identity", "issue"])
        self.assertEqual(attempt.password, bytearray(len(attempt.password)))
        self.assertNotIn("synthetic-pass", repr(attempt))

    def test_unknown_disabled_and_wrong_password_share_error(self):
        for name, actor, session_error in (
            ("unknown", uuid.uuid4(), None),
            ("Alice", None, None),
            ("Alice", uuid.uuid4(), "AUTH_ACCESS_DENIED"),
        ):
            with self.subTest(name=name, actor=actor, session_error=session_error):
                self.setUp()
                self.deps.actor = actor
                self.deps.session_error = session_error
                attempt = self.attempt(name)
                with self.assertRaises(LoginError) as caught:
                    self.service.login(attempt)
                self.assertEqual(caught.exception.code, "AUTH_INVALID_CREDENTIALS")
                self.assertEqual(self.deps.last_event.action, "AUTH_LOGIN_DENIED")
                self.assertEqual(self.deps.commits, 1)
                self.assertEqual(attempt.password, bytearray(len(attempt.password)))

    def test_rate_denial_precedes_lookup_and_erase(self):
        self.deps.rate_error = "AUTH_RATE_LIMITED"
        attempt = self.attempt()
        with self.assertRaises(LoginError) as caught:
            self.service.login(attempt)
        self.assertEqual(caught.exception.code, "AUTH_RATE_LIMITED")
        self.assertEqual(self.deps.calls, ["rate"])
        self.assertEqual(attempt.password, bytearray(len(attempt.password)))

    def test_audit_or_session_infrastructure_failure_fails_closed(self):
        self.deps.actor = None
        self.deps.audit_error = True
        with self.assertRaises(LoginError) as caught:
            self.service.login(self.attempt())
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")
        self.setUp()
        self.deps.session_error = "AUTH_ENTROPY_UNAVAILABLE"
        with self.assertRaises(LoginError) as caught:
            self.service.login(self.attempt())
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")

    def test_malformed_username_still_uses_dummy(self):
        attempt = self.attempt("\x00")
        with self.assertRaises(LoginError) as caught:
            self.service.login(attempt)
        self.assertEqual(caught.exception.code, "AUTH_INVALID_CREDENTIALS")
        self.assertEqual(self.deps.calls, ["rate", "dummy", "audit"])

    def test_dependency_and_invalid_request_fail_closed(self):
        with self.assertRaises(ValueError):
            LoginService(unit_of_work=None, rate=self.deps, identity=self.deps,
                         missing_verifier=self.deps, sessions=self.deps, audit=self.deps)
        bad = LoginAttempt("Alice", bytearray(b"synthetic-pass"), "127.0.0.1", uuid.UUID(int=0))
        with self.assertRaises(LoginError) as caught:
            self.service.login(bad)
        self.assertEqual(caught.exception.code, "AUTH_INVALID_CREDENTIALS")
        self.assertEqual(bad.password, bytearray(len(bad.password)))

    def test_rate_identity_and_dummy_outages_do_not_issue(self):
        for mode in ("rate", "identity", "dummy"):
            with self.subTest(mode=mode):
                self.setUp()
                if mode == "rate":
                    self.deps.rate_unexpected = True
                elif mode == "identity":
                    self.deps.identity_error = True
                else:
                    self.deps.dummy_error = True
                attempt = self.attempt("unknown" if mode == "dummy" else "Alice")
                with self.assertRaises(LoginError) as caught:
                    self.service.login(attempt)
                self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")
                self.assertEqual(attempt.password, bytearray(len(attempt.password)))
                self.assertNotIn("issue", self.deps.calls)

    def test_invalid_identity_and_session_runtime_failure(self):
        self.deps.actor = "not-a-user-id"
        with self.assertRaises(LoginError) as caught:
            self.service.login(self.attempt())
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")
        self.setUp()
        self.deps.session_error = "RUNTIME"
        with self.assertRaises(LoginError) as caught:
            self.service.login(self.attempt())
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
