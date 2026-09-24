from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.license.application.installation_activation import (
    ActivateLicense, ActivatedLicense, LicenseActivationError, LicenseActivationService,
)
from plm_assistant.modules.license.application.validation_recording import RecordedValidation


class Transaction:
    def __init__(self, store):
        self.store = store
        self.committed = False
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.committed and self.result:
            self.store.activations.append(self.result)

    def commit(self):
        self.committed = True


class Store:
    def __init__(self):
        self.activations = []
        self.accept = True

    def uow(self):
        return Transaction(self)

    def activate(self, tx, **values):
        if not self.accept:
            return None
        tx.result = ActivatedLicense(values["installation_id"], None, values["event_id"], 0)
        return tx.result


class Access:
    def __init__(self):
        self.actor = uuid.uuid4()
        self.calls = 0

    def authorized_admin(self, tx, **kwargs):
        self.calls += 1
        return self.actor


class Recorder:
    def __init__(self):
        self.code = "VALID"
        self.calls = 0

    def record_imported(self, installation_id, **kwargs):
        self.calls += 1
        return RecordedValidation(installation_id, uuid.uuid4(), self.code,
                                  kwargs["expected_lock_version"] + 1)


class Audit:
    def __init__(self):
        self.fail = False

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("audit unavailable")
        assert event.action == "LICENSE_ACTIVATED"


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.store, self.access, self.recorder, self.audit = Store(), Access(), Recorder(), Audit()
        self.service = LicenseActivationService(
            unit_of_work=self.store.uow, access=self.access, recorder=self.recorder,
            repository=self.store, audit=self.audit,
            clock=lambda: datetime(2026, 9, 24, tzinfo=timezone.utc),
        )
        self.command = ActivateLicense(b"a" * 32, b"b" * 32, uuid.uuid4(), 0, 1, uuid.uuid4())

    def test_fresh_validation_then_activation(self):
        result = self.service.activate_imported(self.command)
        self.assertEqual(result.installation_id, self.command.installation_id)
        self.assertEqual(self.access.calls, 2)
        self.assertEqual(self.recorder.calls, 1)
        self.assertEqual(len(self.store.activations), 1)

    def test_unauthorized_before_validation(self):
        self.access.actor = None
        with self.assertRaises(LicenseActivationError) as caught:
            self.service.activate_imported(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.recorder.calls, 0)

    def test_denied_validation_never_activates(self):
        self.recorder.code = "MACHINE_MISMATCH"
        with self.assertRaises(LicenseActivationError) as caught:
            self.service.activate_imported(self.command)
        self.assertEqual(caught.exception.code, "MACHINE_MISMATCH")
        self.assertEqual(self.store.activations, [])

    def test_lost_permission_after_validation(self):
        access = self.access
        original = access.authorized_admin
        access.authorized_admin = lambda *args, **kwargs: original(*args, **kwargs) if access.calls == 0 else None
        with self.assertRaises(LicenseActivationError):
            self.service.activate_imported(self.command)
        self.assertEqual(self.store.activations, [])

    def test_audit_failure_rolls_back(self):
        self.audit.fail = True
        with self.assertRaises(RuntimeError):
            self.service.activate_imported(self.command)
        self.assertEqual(self.store.activations, [])

    def test_repository_conflict_fails_closed(self):
        self.store.accept = False
        with self.assertRaises(LicenseActivationError) as caught:
            self.service.activate_imported(self.command)
        self.assertEqual(caught.exception.code, "INSTALLATION_CONFLICT")
        self.assertEqual(self.store.activations, [])

    def test_invalid_command_does_not_validate(self):
        with self.assertRaises(LicenseActivationError) as caught:
            self.service.activate_imported(ActivateLicense(b"short", b"b" * 32,
                                                           self.command.installation_id, 0, 1,
                                                           self.command.trace_id))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.recorder.calls, 0)

    def test_inconsistent_recorded_result_fails_closed(self):
        self.recorder.record_imported = lambda installation_id, **kwargs: RecordedValidation(
            installation_id, uuid.uuid4(), "VALID", 99,
        )
        with self.assertRaises(LicenseActivationError) as caught:
            self.service.activate_imported(self.command)
        self.assertEqual(caught.exception.code, "TRUST_STATE_INVALID")
        self.assertEqual(self.store.activations, [])


if __name__ == "__main__":
    unittest.main()
