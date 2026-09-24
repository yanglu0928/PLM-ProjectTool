from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.auth.application.initial_admin import (
    InitializeAdmin, InitialAdminError, InitialAdminService,
)
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult


class Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class Repository:
    def __init__(self):
        self.empty = True
        self.created = []

    def claim_empty(self, transaction):
        return self.empty

    def create(self, transaction, **kwargs):
        self.created.append(kwargs)
        return uuid.uuid4()


class Hasher:
    def hash_password(self, password):
        return PasswordHashResult("synthetic-hash", "SCRYPT", {"n": 131072})


class Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, transaction, event):
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(event)


class InitialAdminTests(unittest.TestCase):
    def setUp(self):
        self.tx = Transaction()
        self.repo = Repository()
        self.audit = Audit()
        self.service = InitialAdminService(unit_of_work=lambda: self.tx,
                                           repository=self.repo, hasher=Hasher(),
                                           audit=self.audit)

    def test_create_only_in_empty_deployment_and_erase_password(self):
        password = bytearray(b"synthetic-long-admin-passphrase")
        user = self.service.initialize(InitializeAdmin(" Admin ", password, uuid.uuid4()))
        self.assertIsInstance(user, uuid.UUID)
        self.assertEqual(password, bytearray(len(password)))
        self.assertEqual(self.repo.created[0]["username_normalized"], "admin")
        self.assertEqual(self.audit.events[0].actor_type, "UNRESOLVED")
        self.assertEqual(self.audit.events[0].target_object_id, user)
        self.assertTrue(self.tx.committed)

    def test_existing_user_fails_closed_before_write(self):
        self.repo.empty = False
        password = bytearray(b"synthetic-long-admin-passphrase")
        with self.assertRaises(InitialAdminError) as caught:
            self.service.initialize(InitializeAdmin("Admin", password, uuid.uuid4()))
        self.assertEqual(caught.exception.code, "AUTH_INITIALIZATION_CLOSED")
        self.assertEqual(password, bytearray(len(password)))
        self.assertEqual(self.repo.created, [])

    def test_short_and_invalid_input_denied(self):
        for password in (b"too-short", b"x" * 15 + b"\x00", b"\xff" * 20):
            candidate = bytearray(password)
            with self.subTest(password_length=len(password)), self.assertRaises(InitialAdminError):
                self.service.initialize(InitializeAdmin("Admin", candidate, uuid.uuid4()))
            self.assertEqual(candidate, bytearray(len(candidate)))
        self.assertEqual(self.repo.created, [])

    def test_audit_failure_never_commits(self):
        self.audit.fail = True
        password = bytearray(b"synthetic-long-admin-passphrase")
        with self.assertRaises(RuntimeError):
            self.service.initialize(InitializeAdmin("Admin", password, uuid.uuid4()))
        self.assertFalse(self.tx.committed)
        self.assertEqual(password, bytearray(len(password)))


if __name__ == "__main__":
    unittest.main()
