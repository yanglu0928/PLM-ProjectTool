from __future__ import annotations

import base64
import hashlib
import json
import unittest
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.license.application.installation_import import (
    ImportLicense, LicenseImportError, LicenseImportService,
)
from plm_assistant.modules.license.application.signature_verifier import LicenseSignatureVerifier
from plm_assistant.modules.license.infrastructure.static_public_keys import StaticPublicKeyResolver


class Transaction:
    def __init__(self, store):
        self.store = store
        self.pending = None
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.committed and self.pending:
            self.store.saved.append(self.pending)

    def commit(self):
        self.committed = True


class Store:
    def __init__(self):
        self.saved = []

    def uow(self):
        return Transaction(self)

    def add_imported(self, tx, **values):
        tx.pending = ("IMPORTED", values)
        return uuid.uuid4()

    def append_rejection(self, tx, **values):
        tx.pending = ("REJECTED", values)
        return uuid.uuid4()


class Access:
    def __init__(self, actor):
        self.actor = actor

    def authorized_admin(self, tx, **kwargs):
        return self.actor


class Key:
    def product_key_ref(self):
        return "synthetic-release"


class Audit:
    def __init__(self):
        self.fail = False
        self.events = []

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("audit failure")
        self.events.append(event)


class LicenseImportTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.signature = LicenseSignatureVerifier(StaticPublicKeyResolver({"synthetic-release": public}))
        self.store, self.audit = Store(), Audit()
        self.access = Access(uuid.uuid4())
        self.service = LicenseImportService(
            unit_of_work=self.store.uow, repository=self.store, access=self.access,
            signature=self.signature, product_key=Key(), audit=self.audit,
            clock=lambda: datetime(2026, 9, 24, tzinfo=timezone.utc),
        )
        payload = {"schema_version": "plm.license.v1"}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = base64.b64encode(self.private.sign(canonical)).decode()
        self.document = json.dumps({"algorithm": "Ed25519", "payload": payload,
                                    "signature": signature}, separators=(",", ":")).encode()
        self.command = ImportLicense(b"a" * 32, b"b" * 32, self.document, uuid.uuid4())

    def test_imported_candidate_only_and_safe_audit(self):
        result = self.service.import_candidate(self.command)
        self.assertEqual(result.code, "IMPORTED")
        self.assertIsNotNone(result.installation_id)
        self.assertIsNone(result.validation_event_id)
        self.assertEqual(self.store.saved[0][0], "IMPORTED")
        self.assertEqual(self.audit.events[0].outcome, "SUCCESS")
        self.assertNotIn("signed_document", repr(self.command))

    def test_bad_signature_records_only_sanitized_rejection(self):
        altered = self.document.replace(b"plm.license.v1", b"plm.license.v2")
        result = self.service.import_candidate(ImportLicense(b"a" * 32, b"b" * 32,
                                                              altered, uuid.uuid4()))
        self.assertEqual(result.code, "SIGNATURE_INVALID")
        self.assertIsNone(result.installation_id)
        self.assertEqual(self.store.saved[0][0], "REJECTED")
        self.assertEqual(self.store.saved[0][1]["document_sha256"], hashlib.sha256(altered).digest())
        self.assertEqual(self.audit.events[0].outcome, "DENIED")

    def test_non_admin_cannot_import_or_record_document(self):
        self.access.actor = None
        with self.assertRaises(LicenseImportError) as caught:
            self.service.import_candidate(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.store.saved, [])

    def test_audit_failure_rolls_back_installation(self):
        self.audit.fail = True
        with self.assertRaises(RuntimeError):
            self.service.import_candidate(self.command)
        self.assertEqual(self.store.saved, [])

    def test_oversized_document_rejected_before_access(self):
        with self.assertRaises(LicenseImportError) as caught:
            self.service.import_candidate(ImportLicense(b"a" * 32, b"b" * 32,
                                                         b"x" * 65537, uuid.uuid4()))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.store.saved, [])


if __name__ == "__main__":
    unittest.main()
