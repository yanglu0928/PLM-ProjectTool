from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from plm_assistant.modules.auth.application.initial_admin import (
    InitializeAdmin, InitialAdminError, InitialAdminService,
)
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult


class Transaction:
    def __init__(self):
        self.committed = False
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True
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

    def _command(self):
        return InitializeAdmin('Synthetic admin', bytearray(b'Synthetic initial admin password'), uuid.uuid4())

    def _denied(self, command, code):
        with self.assertRaises(InitialAdminError) as caught:
            self.service.initialize(command)
        self.assertEqual(caught.exception.code, code)
        self.assertFalse(self.tx.committed)
        self.assertFalse(any(command.password))

    def test_all_dependencies_none_refuse_before_transaction(self):
        deps = dict(unit_of_work=Mock(), repository=self.repo, hasher=Hasher(), audit=self.audit)
        for field in deps:
            with self.subTest(field=field), self.assertRaises(ValueError):
                InitialAdminService(**(deps | {field: None}))
        deps['unit_of_work'].assert_not_called()

    def test_claim_requires_exact_true_without_hash_or_write(self):
        for value in (None, 1, 'yes', object()):
            self.setUp()
            self.repo.empty = value
            self.service._hasher = Mock()
            command = self._command()
            with self.subTest(claim_type=type(value).__name__):
                self._denied(command, 'AUTH_INITIALIZATION_CLOSED')
                self.service._hasher.hash_password.assert_not_called()
                self.assertEqual(self.repo.created, [])
                self.assertTrue(self.tx.closed)

    def test_utf8_byte_length_does_not_replace_character_minimum(self):
        command = replace(self._command(), password=bytearray(('中' * 5).encode('utf-8')))
        self.service._uow = Mock()
        self._denied(command, 'VALIDATION_FAILED')
        self.service._uow.assert_not_called()

    def test_invalid_commands_erase_before_transaction(self):
        for kind in ('trace_none', 'trace_bool', 'trace_zero', 'username', 'oversized', 'wrong_command'):
            self.setUp()
            command = self._command()
            if kind.startswith('trace_'):
                command = replace(command, trace_id={'trace_none':None, 'trace_bool':True,
                                                     'trace_zero':uuid.UUID(int=0)}[kind])
            elif kind == 'username': command = replace(command, username='')
            elif kind == 'oversized': command = replace(command, password=bytearray(b'x' * 1025))
            else: command = SimpleNamespace(password=command.password)
            self.service._uow = Mock()
            with self.subTest(kind=kind):
                self._denied(command, 'VALIDATION_FAILED')
                self.service._uow.assert_not_called()

    def test_malformed_hash_refuses_before_create_and_erases(self):
        for value in (None, PasswordHashResult('', 'SCRYPT', {}), PasswordHashResult(True, 'SCRYPT', {}),
                      PasswordHashResult('x' * 1025, 'SCRYPT', {}), PasswordHashResult('x', 'OTHER', {}),
                      PasswordHashResult('x', 'SCRYPT', None)):
            self.setUp()
            self.service._hasher = Mock()
            self.service._hasher.hash_password.return_value = value
            with self.subTest(hash_type=type(value).__name__):
                self._denied(self._command(), 'SYSTEM_UNAVAILABLE')
                self.assertEqual(self.repo.created, [])
                self.assertEqual(self.audit.events, [])
                self.assertTrue(self.tx.closed)

    def test_hasher_exception_erases_and_memoryview_is_released(self):
        self.service._hasher = Mock()
        views = []
        def fail(view):
            views.append(view)
            raise RuntimeError('Synthetic private hash failure')
        self.service._hasher.hash_password.side_effect = fail
        self._denied(self._command(), 'SYSTEM_UNAVAILABLE')
        self.assertEqual(len(views), 1)
        with self.assertRaises(ValueError):
            len(views[0])
        self.assertTrue(self.tx.closed)

    def test_original_repository_audit_commit_exceptions_exit_and_erase(self):
        for stage in ('claim', 'create', 'audit', 'commit'):
            self.setUp()
            command = self._command()
            fault = Mock(side_effect=RuntimeError('Synthetic private source failure'))
            if stage == 'claim': self.repo.claim_empty = fault
            elif stage == 'create': self.repo.create = fault
            elif stage == 'audit': self.audit.append = fault
            else: self.tx.commit = fault
            with self.subTest(stage=stage), self.assertRaises(RuntimeError):
                self.service.initialize(command)
            self.assertFalse(self.tx.committed)
            self.assertTrue(self.tx.closed)
            self.assertFalse(any(command.password))


if __name__ == "__main__":
    unittest.main()
