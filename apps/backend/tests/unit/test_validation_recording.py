from __future__ import annotations

import hashlib
import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.license.application.license_validation import LicenseValidationError, VerifiedFullBundleLicense
from plm_assistant.modules.license.application.validation_recording import ImportedDocument, ValidationRecordingError, ValidationRecordingService


class Transaction:
    def __init__(self, store):
        self.store = store
        self.pending = None
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.committed and self.pending:
            source = self.store.source
            self.store.source = ImportedDocument(source.installation_id, source.public_key_ref,
                                                 source.lock_version + 1, source.signed_document,
                                                 source.document_sha256)
            self.store.saved.append(self.pending)

    def commit(self):
        self.committed = True


class Repository:
    def __init__(self, source):
        self.source = source
        self.saved = []
        self.conflict = False

    def uow(self):
        return Transaction(self)

    def read_imported(self, tx, installation_id):
        return self.source if self.source.installation_id == installation_id else None

    def append_result(self, tx, **values):
        tx.pending = values
        return uuid.uuid4()

    def attach_result(self, tx, **values):
        return not self.conflict


class Validator:
    def __init__(self, code=None):
        self.code = code
        self.calls = []

    def validate(self, document, **kwargs):
        self.calls.append((document, kwargs))
        if self.code:
            raise LicenseValidationError(self.code)
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        return VerifiedFullBundleLicense("synthetic", "synthetic", hashlib.sha256(document).digest(),
                                         b"a" * 32, now, now, now)


class Audit:
    def __init__(self, fail=False):
        self.fail = fail
        self.events = []

    def append(self, tx, draft):
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(draft)


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.installation_id = uuid.uuid4()
        self.document = b"synthetic-document"
        self.store = Repository(ImportedDocument(self.installation_id, "release-v1", 0,
                                                  self.document, hashlib.sha256(self.document).digest()))
        self.validator = Validator()
        self.audit = Audit()
        self.service = ValidationRecordingService(self.store.uow, self.store, self.validator, self.audit)
        self.trace = uuid.uuid4()

    def record(self):
        return self.service.record_imported(self.installation_id, expected_lock_version=0,
                                            expected_time_version=1, trace_id=self.trace)

    def test_verified_result_and_safe_audit(self):
        result = self.record()
        self.assertEqual((result.code, result.lock_version), ("VALID", 1))
        self.assertEqual(self.validator.calls[0][1]["expected_public_key_ref"], "release-v1")
        self.assertEqual(self.audit.events[0].outcome, "SUCCESS")
        self.assertEqual(self.store.saved[0]["verified"].grant_scope, "FULL_BUNDLE")

    def test_denial_has_no_entitlement(self):
        self.validator.code = "SIGNATURE_INVALID"
        self.assertEqual(self.record().code, "SIGNATURE_INVALID")
        self.assertIsNone(self.store.saved[0]["verified"])
        self.assertEqual(self.audit.events[0].outcome, "DENIED")

    def test_corruption_never_reaches_verifier(self):
        self.store.source = ImportedDocument(self.installation_id, "release-v1", 0,
                                             self.document, b"x" * 32)
        self.assertEqual(self.record().code, "TRUST_STATE_INVALID")
        self.assertEqual(self.validator.calls, [])
        self.assertIsNone(self.store.saved[0]["document_sha256"])

    def test_conflict_rolls_back(self):
        self.store.conflict = True
        with self.assertRaises(ValidationRecordingError):
            self.record()
        self.assertEqual(self.store.saved, [])

    def test_audit_failure_rolls_back(self):
        self.audit.fail = True
        with self.assertRaises(RuntimeError):
            self.record()
        self.assertEqual(self.store.saved, [])
        self.assertEqual(self.store.source.lock_version, 0)


if __name__ == "__main__":
    unittest.main()
