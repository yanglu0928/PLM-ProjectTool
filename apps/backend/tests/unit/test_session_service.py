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
    def lock_user(self, tx, user_id):
        return user_id == USER

    def revoke_user_sessions(self, tx, user_id, now, reason):
        count = 0
        for row in tx.working["rows"]:
            if row["revoked_at"] is None:
                row["revoked_at"] = now
                row["reason"] = reason
                count += 1
        return count

    def current_credential_version(self, tx, user_id):
        return tx.working["version"] if tx.working["state"] == "ENABLED" else None

    def create(self, tx, **values):
        session_id = SESSION if not tx.working["rows"] else uuid.uuid4()
        row = dict(values, session_id=session_id, revoked_at=None)
        tx.working["row"] = row
        tx.working["rows"].append(row)
        return session_id

    def find_by_token_digest(self, tx, digest):
        row = next((item for item in tx.working["rows"] if item["token_digest"] == digest), None)
        if row is None:
            return None
        return SessionRecord(row["session_id"], USER, row["credential_version"], row["csrf_digest"],
                             row["absolute_expires_at"], row["idle_expires_at"],
                             row["revoked_at"], tx.working["state"], tx.working["version"])

    def revoke(self, tx, session_id, now, reason):
        row = next((item for item in tx.working["rows"] if item["session_id"] == session_id), None)
        if row is None or row["revoked_at"] is not None:
            return False
        row["revoked_at"] = now
        row["reason"] = reason
        return True


class FakeAccess:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def can_issue(self, tx, user_id, credential_version, proof):
        return self.allowed and proof is True


class FakeAdminAccess:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def can_revoke_user_sessions(self, tx, actor_id, user_id):
        return self.allowed


class FakeAudit:
    def __init__(self, fail=False):
        self.fail = fail

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("audit unavailable")
        tx.working["audit"].append(event)
        return uuid.uuid4()


def make_service(*, allowed=True, admin_access=None, fail_audit=False, clock=None, random_bytes=None):
    store = {"version": 1, "state": "ENABLED", "row": None, "rows": [], "audit": []}
    service = SessionService(
        unit_of_work=lambda: FakeUow(store), repository=FakeRepo(),
        issue_access=FakeAccess(allowed), admin_access=admin_access, audit=FakeAudit(fail_audit),
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

    def test_renew_rotates_both_secrets_and_retires_old_pair(self):
        values = iter((b"a" * 32, b"b" * 32, b"c" * 32, b"d" * 32))
        service, store = make_service(random_bytes=lambda n: next(values))
        old = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        renewed = service.renew(token=old.token, csrf_token=old.csrf_token, trace_id=TRACE)
        self.assertNotEqual(old.session_id, renewed.session_id)
        self.assertNotEqual(old.token, renewed.token)
        self.assertNotEqual(old.csrf_token, renewed.csrf_token)
        self.assertEqual(old.absolute_expires_at, renewed.absolute_expires_at)
        self.assertEqual(store["rows"][0]["reason"], "RENEWED")
        self.assertEqual(store["audit"][-1].action, "SESSION_RENEWED")
        with self.assertRaises(SessionError):
            service.validate(old.token)
        self.assertEqual(service.validate(renewed.token, csrf_token=renewed.csrf_token, require_csrf=True).user_id, USER)

    def test_renew_wrong_csrf_and_audit_failure_leave_old_active(self):
        values = iter((b"a" * 32, b"b" * 32, b"c" * 32, b"d" * 32))
        service, store = make_service(random_bytes=lambda n: next(values))
        old = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        with self.assertRaises(SessionError):
            service.renew(token=old.token, csrf_token=b"x" * 32, trace_id=TRACE)
        service._audit.fail = True
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            service.renew(token=old.token, csrf_token=old.csrf_token, trace_id=TRACE)
        self.assertEqual(len(store["rows"]), 1)
        self.assertIsNone(store["row"]["revoked_at"])
        self.assertEqual(service.validate(old.token).user_id, USER)

    def test_renew_entropy_reuse_fails_before_revocation(self):
        values = iter((b"a" * 32, b"b" * 32, b"a" * 32, b"d" * 32))
        service, store = make_service(random_bytes=lambda n: next(values))
        old = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        with self.assertRaises(SessionError) as caught:
            service.renew(token=old.token, csrf_token=old.csrf_token, trace_id=TRACE)
        self.assertEqual(caught.exception.code, "AUTH_ENTROPY_UNAVAILABLE")
        self.assertIsNone(store["row"]["revoked_at"])

    def test_admin_revoke_requires_access_and_is_audited(self):
        values = iter((b"a" * 32, b"b" * 32, b"c" * 32, b"d" * 32))
        service, store = make_service(admin_access=FakeAdminAccess(False), random_bytes=lambda n: next(values))
        first = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        second = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        with self.assertRaises(SessionError):
            service.revoke_user_sessions(actor_id=USER, user_id=USER, trace_id=TRACE)
        self.assertIsNone(store["rows"][0]["revoked_at"])
        service._admin_access.allowed = True
        self.assertEqual(service.revoke_user_sessions(actor_id=USER, user_id=USER, trace_id=TRACE), 2)
        self.assertEqual(service.revoke_user_sessions(actor_id=USER, user_id=USER, trace_id=TRACE), 0)
        self.assertEqual(store["audit"][-1].action, "USER_SESSIONS_REVOKED")
        for issued in (first, second):
            with self.assertRaises(SessionError):
                service.validate(issued.token)

    def test_admin_revoke_audit_failure_rolls_back(self):
        values = iter((b"a" * 32, b"b" * 32))
        service, store = make_service(admin_access=FakeAdminAccess(), random_bytes=lambda n: next(values))
        issued = service.issue(user_id=USER, trace_id=TRACE, proof=True)
        service._audit.fail = True
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            service.revoke_user_sessions(actor_id=USER, user_id=USER, trace_id=TRACE)
        self.assertEqual(service.validate(issued.token).user_id, USER)

    def test_admin_revoke_unavailable_without_adapter(self):
        service, _ = make_service()
        with self.assertRaises(SessionError) as caught:
            service.revoke_user_sessions(actor_id=USER, user_id=USER, trace_id=TRACE)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")

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
