from __future__ import annotations

import copy
import hashlib
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionPolicy, SessionRecord, SessionService,
)


USER = uuid.uuid4()
TRACE = uuid.uuid4()
SESSION = uuid.uuid4()
NOW = datetime(2026, 9, 24, 9, tzinfo=timezone.utc)


class FakeUow:
    def __init__(self, store):
        self.store = store
        self.working = copy.deepcopy(store)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.store.clear()
        self.store.update(self.working)


class FakeRepo:
    def current_credential_version(self, tx, user_id):
        return tx.working["version"] if tx.working["state"] == "ENABLED" else None

    def create(self, tx, **values):
        tx.working["row"] = dict(values, session_id=SESSION, revoked_at=None)
        return SESSION

    def find_by_token_digest(self, tx, digest):
        row = tx.working["row"]
        if row is None or row["token_digest"] != digest:
            return None
        return SessionRecord(SESSION, USER, row["credential_version"], row["csrf_digest"],
                             row["absolute_expires_at"], row["idle_expires_at"],
                             row["revoked_at"], tx.working["state"], tx.working["version"])

    def revoke(self, tx, session_id, now, reason):
        if tx.working["row"]["revoked_at"] is not None:
            return False
        tx.working["row"]["revoked_at"] = now
        tx.working["row"]["reason"] = reason
        return True


class FakeAccess:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def can_issue(self, tx, user_id, credential_version, proof):
        return self.allowed and proof is True


class FakeAudit:
    def __init__(self, fail=False):
        self.fail = fail

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("audit unavailable")
        tx.working["audit"].append(event)
        return uuid.uuid4()


def make_service(*, allowed=True, fail_audit=False, clock=None, random_bytes=None):
    store = {"version": 1, "state": "ENABLED", "row": None, "audit": []}
    service = SessionService(
        unit_of_work=lambda: FakeUow(store), repository=FakeRepo(),
        issue_access=FakeAccess(allowed), audit=FakeAudit(fail_audit),
        clock=clock or (lambda: NOW), random_bytes=random_bytes or (lambda n: b"a" * n if not store["row"] else b"c" * n),
    )
    return service, store


class SessionServiceTests(unittest.TestCase):
    def test_issue_validate_revoke_and_no_raw_storage_or_repr(self):
        values = iter((b"a" * 32, b"b" * 32))
        service, store = make_service(random_bytes=lambda n: next(values))
        issued = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        self.assertNotIn("aaaaaaaa", repr(issued))
        self.assertNotIn("bbbbbbbb", repr(issued))
        self.assertEqual(store["row"]["token_digest"], hashlib.sha256(issued.token).digest())
        self.assertEqual(store["row"]["csrf_digest"], hashlib.sha256(issued.csrf_token).digest())
        self.assertEqual(store["audit"][0].action, "SESSION_ISSUED")
        self.assertEqual(service.validate(issued.token, csrf_token=issued.csrf_token, require_csrf=True).user_id, USER)
        with self.assertRaises(SessionError):
            service.validate(issued.token, csrf_token=b"x" * 32, require_csrf=True)
        self.assertTrue(service.revoke(token=issued.token, csrf_token=issued.csrf_token, trace_id=TRACE))
        self.assertEqual(store["row"]["reason"], "LOGOUT")
        self.assertEqual(store["audit"][1].action, "SESSION_REVOKED")
        with self.assertRaises(SessionError):
            service.validate(issued.token)

    def test_issue_requires_access_and_enabled_user(self):
        service, store = make_service(allowed=False)
        with self.assertRaises(SessionError):
            service.issue(user_id=USER, trace_id=TRACE, proof=True)
        self.assertIsNone(store["row"])
        service, store = make_service()
        store["state"] = "DISABLED"
        with self.assertRaises(SessionError):
            service.issue(user_id=USER, trace_id=TRACE, proof=True)
        self.assertIsNone(store["row"])

    def test_user_disable_credential_change_and_expiry_fail_closed(self):
        values = iter((b"a" * 32, b"b" * 32))
        moment = [NOW]
        service, store = make_service(clock=lambda: moment[0], random_bytes=lambda n: next(values))
        issued = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        for state, version in (("DISABLED", 1), ("ENABLED", 2)):
            store.update(state=state, version=version)
            with self.assertRaises(SessionError) as caught:
                service.validate(issued.token)
            self.assertEqual(caught.exception.code, "AUTH_SESSION_EXPIRED")
        store.update(state="ENABLED", version=1)
        moment[0] = NOW + timedelta(minutes=30)
        with self.assertRaises(SessionError):
            service.validate(issued.token)

    def test_failed_audit_rolls_back_issue_and_revoke(self):
        values = iter((b"a" * 32, b"b" * 32))
        service, store = make_service(fail_audit=True, random_bytes=lambda n: next(values))
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            service.issue(user_id=USER, trace_id=TRACE, proof=True)
        self.assertIsNone(store["row"])
        self.assertEqual(store["audit"], [])

    def test_bad_entropy_clock_policy_and_token_rejected(self):
        service, _ = make_service(random_bytes=lambda n: b"a" * n)
        with self.assertRaises(SessionError):
            service.issue(user_id=USER, trace_id=TRACE, proof=True)
        service, _ = make_service(clock=lambda: datetime(2026, 9, 24))
        with self.assertRaises(SessionError):
            service.issue(user_id=USER, trace_id=TRACE, proof=True)
        with self.assertRaises(ValueError):
            SessionPolicy(idle_lifetime=timedelta(hours=25))
        with self.assertRaises(SessionError):
            service.validate(b"short")


if __name__ == "__main__":
    unittest.main()
