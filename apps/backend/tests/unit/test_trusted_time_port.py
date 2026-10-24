from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.license.application.trusted_time import TrustedTimeError, TrustedTimeRecord, TrustedTimeStatePort
from plm_assistant.modules.license.infrastructure.trusted_time_repository import SqlAlchemyTrustedTimeRepository


class FakeTransaction:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        pass


class FakeRepository:
    def __init__(self, record: TrustedTimeRecord | None, *, write_ok: bool = True, read_error: bool = False):
        self.record = record
        self.write_ok = write_ok
        self.read_error = read_error
        self.events: list[str] = []

    def read_locked(self, _tx):
        if self.read_error:
            raise RuntimeError("synthetic database failure")
        return self.record

    def append_event(self, _tx, *, code, candidate, trace_id):
        self.events.append(code)
        return uuid.uuid4()

    def advance(self, _tx, **_kwargs):
        return self.write_ok


class FakeIntegrity:
    def verify(self, _record):
        return True

    def sign(self, _record):
        return {"tag": "synthetic"}


class FakeAudit:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.events = []

    def append(self, _tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.events.append(event)


class TrustedTimePortTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        self.trace = uuid.uuid4()
        self.state = TrustedTimeRecord(uuid.uuid4(), None, 0, None, None)

    def port(self, repository, audit=None):
        return TrustedTimeStatePort(FakeTransaction, repository, FakeIntegrity(), audit or FakeAudit())

    def test_invalid_inputs_and_missing_dependencies_fail_closed(self):
        with self.assertRaises(ValueError):
            TrustedTimeStatePort(None, FakeRepository(self.state), FakeIntegrity(), FakeAudit())
        port = self.port(FakeRepository(self.state))
        for candidate, version in ((self.now.replace(tzinfo=None), 0), (self.now, -1), (self.now, True)):
            with self.assertRaises(TrustedTimeError) as caught:
                port.advance(candidate=candidate, expected_version=version, trace_id=self.trace)
            self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")

    def test_missing_state_and_failed_cas_are_durable_denials(self):
        missing = FakeRepository(None)
        with self.assertRaises(TrustedTimeError) as caught:
            self.port(missing).advance(candidate=self.now, expected_version=0, trace_id=self.trace)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(missing.events, ["INTEGRITY_REJECTED"])
        stale = FakeRepository(self.state, write_ok=False)
        with self.assertRaises(TrustedTimeError) as caught:
            self.port(stale).advance(candidate=self.now, expected_version=0, trace_id=self.trace)
        self.assertEqual(caught.exception.code, "TRUST_STATE_CONFLICT")
        self.assertEqual(stale.events, ["ADVANCED", "CONFLICT_REJECTED"])

    def test_repository_or_audit_failure_never_returns_success(self):
        repo = FakeRepository(self.state, read_error=True)
        with self.assertRaises(TrustedTimeError) as caught:
            self.port(repo).advance(candidate=self.now, expected_version=0, trace_id=self.trace)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(repo.events, ["INTEGRITY_REJECTED"])
        with self.assertRaises(TrustedTimeError) as caught:
            self.port(FakeRepository(self.state), FakeAudit(fail=True)).advance(
                candidate=self.now, expected_version=0, trace_id=self.trace)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")

    def test_repository_requires_active_transaction(self):
        repo = SqlAlchemyTrustedTimeRepository()
        with self.assertRaises(RuntimeError):
            repo.read_locked(object())

    def test_current_version_requires_verified_state(self):
        self.assertEqual(self.port(FakeRepository(self.state)).current_verified_version(), 0)
        broken_integrity = self.port(FakeRepository(self.state))
        broken_integrity._integrity.verify = lambda _record: False
        with self.assertRaises(TrustedTimeError) as invalid:
            broken_integrity.current_verified_version()
        self.assertEqual(invalid.exception.code, "TRUST_STATE_INVALID")
        with self.assertRaises(TrustedTimeError) as missing:
            self.port(FakeRepository(None)).current_verified_version()
        self.assertEqual(missing.exception.code, "TRUST_STATE_INVALID")
        with self.assertRaises(TrustedTimeError) as broken:
            self.port(FakeRepository(self.state, read_error=True)).current_verified_version()
        self.assertEqual(broken.exception.code, "TRUST_STATE_INVALID")


if __name__ == "__main__":
    unittest.main()
