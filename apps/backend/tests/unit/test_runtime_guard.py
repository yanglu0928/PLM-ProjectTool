from __future__ import annotations

import hashlib
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.license.application.license_validation import LicenseValidationError, VerifiedFullBundleLicense
from plm_assistant.modules.license.application.runtime_guard import (
    LicenseRuntimeGuard, RuntimeLicenseError, RuntimeLicenseSnapshot,
)


NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
DOCUMENT = b"synthetic-signed-document"


class Transaction:
    def __init__(self, repository):
        self.repository = repository
        self.pending = None
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.committed and self.pending:
            self.repository.events.append(self.pending)

    def commit(self):
        self.committed = True


class Repository:
    def __init__(self):
        self.snapshot = RuntimeLicenseSnapshot(
            "VALID", uuid.uuid4(), 0, uuid.uuid4(), uuid.uuid4(), "release-v1",
            DOCUMENT, hashlib.sha256(DOCUMENT).digest(), b"a" * 32,
            {"product_code": "PLM_PROJECT_TOOL", "grant_scope": "FULL_BUNDLE",
             "valid_from": (NOW - timedelta(days=1)).isoformat(),
             "valid_to": (NOW + timedelta(days=1)).isoformat()},
        )
        self.events = []
        self.accept = True

    def uow(self):
        return Transaction(self)

    def read_current(self, tx):
        return self.snapshot

    def record_check(self, tx, **values):
        if not self.accept:
            return False
        tx.pending = values
        return True


class TrustedTime:
    def __init__(self):
        self.fail = False

    def current_verified_version(self):
        if self.fail:
            raise RuntimeError("synthetic trust failure")
        return 3


class Validator:
    def __init__(self):
        self.code = None
        self.calls = []

    def validate(self, document, **kwargs):
        self.calls.append(kwargs)
        if self.code:
            raise LicenseValidationError(self.code)
        return VerifiedFullBundleLicense(
            "synthetic", "synthetic", hashlib.sha256(document).digest(), b"a" * 32,
            NOW - timedelta(days=1), NOW + timedelta(days=1), NOW,
        )


class Audit:
    def __init__(self):
        self.fail = False
        self.events = []

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(event)


class RuntimeGuardTests(unittest.TestCase):
    def setUp(self):
        self.repository, self.trusted, self.validator, self.audit = Repository(), TrustedTime(), Validator(), Audit()
        self.guard = LicenseRuntimeGuard(
            unit_of_work=self.repository.uow, repository=self.repository,
            validator=self.validator, trusted_time=self.trusted, audit=self.audit,
            clock=lambda: NOW,
        )
        self.trace = uuid.uuid4()

    def test_valid_requires_full_verification_and_record(self):
        result = self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(result.grant_scope, "FULL_BUNDLE")
        self.assertEqual(self.validator.calls[0]["expected_time_version"], 3)
        self.assertEqual(self.repository.events[0]["code"], "VALID")
        self.assertEqual(self.audit.events[0].outcome, "SUCCESS")

    def test_not_installed_denies_without_validator(self):
        self.repository.snapshot = RuntimeLicenseSnapshot("NOT_INSTALLED")
        with self.assertRaises(RuntimeLicenseError) as caught:
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(caught.exception.code, "NOT_INSTALLED")
        self.assertEqual(self.validator.calls, [])

    def test_expired_denial_is_recorded(self):
        self.validator.code = "EXPIRED"
        with self.assertRaises(RuntimeLicenseError) as caught:
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(caught.exception.code, "EXPIRED")
        self.assertEqual(self.repository.events[0]["code"], "EXPIRED")
        self.assertIsNone(self.repository.events[0]["verified"])

    def test_trusted_time_failure_denies(self):
        self.trusted.fail = True
        with self.assertRaises(RuntimeLicenseError) as caught:
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.repository.events[0]["code"], "TRUST_STATE_INVALID")

    def test_projection_mismatch_denies(self):
        source = self.repository.snapshot
        self.repository.snapshot = RuntimeLicenseSnapshot(
            source.code, source.state_id, source.state_version, source.installation_id,
            source.current_event_id, source.public_key_ref, source.signed_document,
            source.document_sha256, b"b" * 32, source.entitlement_snapshot,
        )
        with self.assertRaises(RuntimeLicenseError):
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(self.repository.events[0]["code"], "TRUST_STATE_INVALID")

    def test_recording_conflict_fails_closed(self):
        self.repository.accept = False
        with self.assertRaises(RuntimeLicenseError):
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(self.repository.events, [])

    def test_audit_failure_rolls_back_and_denies(self):
        self.audit.fail = True
        with self.assertRaises(RuntimeLicenseError):
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(self.repository.events, [])

    def test_invalid_trace_fails_before_database_read(self):
        with self.assertRaises(RuntimeLicenseError) as caught:
            self.guard.require_valid(trace_id=uuid.UUID(int=0))
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")

    def test_incomplete_valid_projection_fails_closed(self):
        self.repository.snapshot = RuntimeLicenseSnapshot("VALID")
        with self.assertRaises(RuntimeLicenseError) as caught:
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.validator.calls, [])

    def test_invalid_clock_fails_before_read(self):
        self.guard._clock = lambda: NOW.replace(tzinfo=None)
        with self.assertRaises(RuntimeLicenseError) as caught:
            self.guard.require_valid(trace_id=self.trace)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")


if __name__ == "__main__":
    unittest.main()
