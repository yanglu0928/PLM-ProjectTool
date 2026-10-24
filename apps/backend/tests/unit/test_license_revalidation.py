from __future__ import annotations

import hashlib
import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.license.application.license_validation import (
    LicenseValidationError, VerifiedFullBundleLicense,
)
from plm_assistant.modules.license.application.revalidation import (
    LicenseRevalidationError, LicenseRevalidationService, RecoverySource,
    RevalidateLicense, RevalidationResult,
)


NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
DOCUMENT = b"synthetic signed test document"


class Tx:
    def __init__(self, store):
        self.store, self.result, self.committed = store, None, False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.committed and self.result is not None:
            self.store.results.append(self.result)

    def commit(self):
        self.committed = True


class Dependencies:
    def __init__(self):
        self.actor = uuid.uuid4()
        self.results = []
        self.source = RecoverySource(uuid.uuid4(), "test-key", DOCUMENT,
                                     hashlib.sha256(DOCUMENT).digest(), 3, 2, uuid.uuid4())
        self.validation_code = "VALID"
        self.time_broken = False
        self.audit_broken = False
        self.validate_calls = 0

    def uow(self):
        return Tx(self)

    def authorized_admin(self, tx, **_):
        return self.actor

    def read_active(self, tx):
        return self.source

    def current_verified_version(self):
        if self.time_broken:
            raise RuntimeError("corrupt HMAC")
        return 5

    def validate(self, document, **kwargs):
        self.validate_calls += 1
        assert document == DOCUMENT
        assert kwargs["expected_public_key_ref"] == "test-key"
        if self.validation_code != "VALID":
            raise LicenseValidationError(self.validation_code)
        return VerifiedFullBundleLicense(
            "test-license", "test customer", hashlib.sha256(DOCUMENT).digest(),
            b"m" * 32, NOW, NOW, NOW,
        )

    def record(self, tx, *, source, code, verified, now, trace_id):
        assert source == self.source
        assert (verified is not None) == (code == "VALID")
        tx.result = RevalidationResult(source.installation_id, uuid.uuid4(), code,
                                       source.state_version + 1)
        return tx.result

    def append(self, tx, event):
        if self.audit_broken:
            raise RuntimeError("audit failure")
        assert event.action == "LICENSE_REVALIDATED"
        assert event.actor_id == self.actor
        assert event.reason_code == tx.result.code


class RevalidationTests(unittest.TestCase):
    def setUp(self):
        self.deps = Dependencies()
        self.service = LicenseRevalidationService(
            unit_of_work=self.deps.uow, access=self.deps, repository=self.deps,
            validator=self.deps, trusted_time=self.deps, audit=self.deps,
            clock=lambda: NOW,
        )
        self.command = RevalidateLicense(b"s" * 32, b"c" * 32, uuid.uuid4())

    def test_full_revalidation_restores_only_after_validation(self):
        result = self.service.revalidate_active(self.command)
        self.assertEqual(result.code, "VALID")
        self.assertEqual(len(self.deps.results), 1)
        self.assertEqual(self.deps.validate_calls, 1)

    def test_expired_license_records_denial(self):
        self.deps.validation_code = "EXPIRED"
        with self.assertRaises(LicenseRevalidationError) as caught:
            self.service.revalidate_active(self.command)
        self.assertEqual(caught.exception.code, "EXPIRED")
        self.assertEqual(self.deps.results[0].code, "EXPIRED")

    def test_trusted_time_damage_cannot_be_repaired_by_revalidation(self):
        self.deps.time_broken = True
        with self.assertRaises(LicenseRevalidationError) as caught:
            self.service.revalidate_active(self.command)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.deps.validate_calls, 0)
        self.assertEqual(self.deps.results[0].code, "TRUST_STATE_INVALID")

    def test_missing_admin_denied_before_source_read(self):
        self.deps.actor = None
        with self.assertRaises(LicenseRevalidationError) as caught:
            self.service.revalidate_active(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.deps.results, [])

    def test_no_active_installation(self):
        self.deps.source = None
        with self.assertRaises(LicenseRevalidationError) as caught:
            self.service.revalidate_active(self.command)
        self.assertEqual(caught.exception.code, "NOT_INSTALLED")

    def test_tampered_document_denied_without_validation(self):
        self.deps.source = RecoverySource(uuid.uuid4(), "test-key", DOCUMENT,
                                          b"x" * 32, 3, 2, uuid.uuid4())
        with self.assertRaises(LicenseRevalidationError) as caught:
            self.service.revalidate_active(self.command)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.deps.validate_calls, 0)

    def test_audit_failure_rolls_back(self):
        self.deps.audit_broken = True
        with self.assertRaises(LicenseRevalidationError) as caught:
            self.service.revalidate_active(self.command)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.deps.results, [])

    def test_invalid_command_does_not_read_state(self):
        with self.assertRaises(LicenseRevalidationError) as caught:
            self.service.revalidate_active(RevalidateLicense(b"short", b"c" * 32, uuid.uuid4()))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.deps.validate_calls, 0)


if __name__ == "__main__":
    unittest.main()
