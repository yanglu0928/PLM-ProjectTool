from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.secret_access import (
    EncryptedSecretDraft, SecretConsumer, SecretPurpose, SecretRef,
)
from plm_assistant.modules.platform.application.secret_write import (
    CreateSecret, RotateSecret, SecretWriteError, SecretWriteService,
)


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
        self.guard_ok = True
        self.current = (SecretPurpose.AI_PROVIDER_KEY, SecretConsumer.AI_PROVIDER_ADAPTER)
        self.commits = 0
        self.writes = 0
        self.encryptions = 0
        self.audit_ok = True

    def unit_of_work(self):
        return Tx(self)

    def authorized_admin(self, tx, **_):
        return self.actor

    def require_valid(self, **_):
        if not self.guard_ok:
            raise RuntimeError("expired synthetic License")

    def encrypt(self, **kwargs):
        self.encryptions += 1
        assert type(kwargs["plaintext"]) is bytearray
        return EncryptedSecretDraft(b"ciphertext", b'{}', "synthetic-key")

    def create(self, tx, **kwargs):
        self.writes += 1
        return uuid.uuid4()

    def lock_current(self, tx, **_):
        return self.current

    def rotate(self, tx, **kwargs):
        self.writes += 1
        return uuid.uuid4()

    def append(self, tx, event):
        if not self.audit_ok:
            raise RuntimeError("audit unavailable")
        assert event.action.startswith("PLATFORM_SECRET_")
        return uuid.uuid4()


class SecretWriteTests(unittest.TestCase):
    def setUp(self):
        self.deps = Deps()
        self.service = SecretWriteService(
            unit_of_work=self.deps.unit_of_work, access=self.deps,
            license_guard=self.deps, repository=self.deps,
            cipher=self.deps, audit=self.deps, clock=lambda: NOW,
        )

    def create_command(self, **changes):
        args = dict(session_token=b"s" * 32, csrf_token=b"c" * 32,
                    purpose=SecretPurpose.AI_PROVIDER_KEY,
                    consumer=SecretConsumer.AI_PROVIDER_ADAPTER,
                    secret_value=bytearray(b"synthetic-only"), trace_id=uuid.uuid4())
        args.update(changes)
        return CreateSecret(**args)

    def rotate_command(self, **changes):
        args = dict(session_token=b"s" * 32, csrf_token=b"c" * 32,
                    secret_ref=SecretRef(uuid.uuid4()), expected_version_no=1,
                    secret_value=bytearray(b"synthetic-next"), trace_id=uuid.uuid4())
        args.update(changes)
        return RotateSecret(**args)

    def test_create_and_rotate_write_only(self):
        command = self.create_command()
        ref = self.service.create(command)
        self.assertIsInstance(ref, SecretRef)
        self.assertEqual(command.secret_value, bytearray(len(command.secret_value)))
        self.assertEqual(self.deps.commits, 1)
        rotate = self.rotate_command(secret_ref=ref)
        self.assertEqual(self.service.rotate(rotate), 2)
        self.assertEqual(rotate.secret_value, bytearray(len(rotate.secret_value)))
        self.assertEqual(self.deps.commits, 2)
        self.assertEqual(self.deps.writes, 2)
        self.assertNotIn("synthetic-only", repr(command))

    def test_auth_license_validation_and_conflict_reject_before_encrypt(self):
        for mode in ("auth", "license", "purpose", "conflict", "csrf"):
            with self.subTest(mode=mode):
                self.setUp()
                if mode == "auth":
                    self.deps.actor = None
                if mode == "license":
                    self.deps.guard_ok = False
                if mode == "conflict":
                    self.deps.current = None
                command = (self.rotate_command() if mode == "conflict"
                           else self.create_command(
                               consumer=SecretConsumer.DATABASE_ADAPTER if mode == "purpose"
                               else SecretConsumer.AI_PROVIDER_ADAPTER,
                               csrf_token=b"short" if mode == "csrf" else b"c" * 32))
                with self.assertRaises(SecretWriteError):
                    self.service.rotate(command) if mode == "conflict" else self.service.create(command)
                self.assertEqual(command.secret_value, bytearray(len(command.secret_value)))
                self.assertEqual(self.deps.encryptions, 0)
                self.assertEqual(self.deps.writes, 0)

    def test_audit_failure_denies_and_clears_input(self):
        self.deps.audit_ok = False
        command = self.create_command()
        with self.assertRaises(SecretWriteError) as caught:
            self.service.create(command)
        self.assertEqual(caught.exception.code, "PLATFORM_SECRET_UNAVAILABLE")
        self.assertEqual(self.deps.commits, 0)
        self.assertEqual(command.secret_value, bytearray(len(command.secret_value)))

    def test_invalid_rotation_version_rejected(self):
        command = self.rotate_command(expected_version_no=0)
        with self.assertRaises(SecretWriteError):
            self.service.rotate(command)
        self.assertEqual(self.deps.encryptions, 0)
        self.assertEqual(command.secret_value, bytearray(len(command.secret_value)))


if __name__ == "__main__":
    unittest.main()
