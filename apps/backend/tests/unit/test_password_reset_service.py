import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.auth.application.password_reset import ResetPassword,PasswordResetService,PasswordResetError
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof


class PasswordResetServiceTests(unittest.TestCase):
    def owner(self,**overrides):
        self.entered=False
        @contextmanager
        def uow():self.entered=True;yield Mock()
        deps=dict(unit_of_work=uow,access=Mock(),repository=Mock(),results=Mock(),replay_verifier=Mock(),
            hasher=Mock(),audit=Mock(),receipts=Mock(),license_guard=Mock())
        return PasswordResetService(**(deps|overrides))

    def command(self):return ResetPassword(b't'*32,b'c'*32,uuid4(),uuid4(),1,True,PasswordResetProof(bytearray(b'Synthetic temporary password')))

    def test_invalid_flag_expected_password_and_key_never_write_and_erase(self):
        for changes,key in (({'must_change_password':1},str(uuid4())),({'must_change_password':False},str(uuid4())),
            ({'expected_version':True},str(uuid4())),({'expected_version':-1},str(uuid4())),
            ({'password':PasswordResetProof(bytearray(b'\xff'))},str(uuid4())),({},'short')):
            owner=self.owner();command=replace(self.command(),**changes)
            with self.assertRaises(PasswordResetError) as caught:owner.reset(command,idempotency_key=key)
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED');self.assertFalse(self.entered)
            self.assertFalse(any(command.password.temporary_password))

    def test_strict_lock_and_unknown_failure_fixed_error(self):
        for value in (False,1,RuntimeError('Synthetic private failure')):
            access=Mock()
            if isinstance(value,Exception):access.lock_deployment.side_effect=value
            else:access.lock_deployment.return_value=value
            owner=self.owner(access=access);command=self.command()
            with self.assertRaises(PasswordResetError) as caught:owner.reset(command,idempotency_key=str(uuid4()))
            self.assertEqual(str(caught.exception),'AUTH_PASSWORD_RESET_UNAVAILABLE')
            access.prove.assert_not_called();self.assertFalse(any(command.password.temporary_password))

    def test_missing_actor_denies_before_hash(self):
        access=Mock();access.lock_deployment.return_value=True;access.prove.return_value=None
        hasher=Mock();owner=self.owner(access=access,hasher=hasher);command=self.command()
        with self.assertRaises(PasswordResetError) as caught:owner.reset(command,idempotency_key=str(uuid4()))
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');hasher.hash_password.assert_not_called()
        self.assertFalse(any(command.password.temporary_password))

    def test_repr_and_error_never_echo_secret(self):
        self.assertNotIn('temporary password',repr(self.command()))
        self.assertEqual(str(PasswordResetError('Synthetic private password')),'AUTH_PASSWORD_RESET_UNAVAILABLE')
