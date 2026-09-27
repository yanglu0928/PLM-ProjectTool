import unittest
from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.auth.application.password_change import ChangePassword,PasswordChangeService,PasswordChangeError
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeProof


class PasswordChangeServiceTests(unittest.TestCase):
    def service(self,**overrides):
        self.entered=False
        @contextmanager
        def uow():
            self.entered=True
            yield Mock()
        deps=dict(unit_of_work=uow,access=Mock(),repository=Mock(),results=Mock(),replay_verifier=Mock(),
            hasher=Mock(),audit=Mock(),receipts=Mock())
        deps.update(overrides)
        return PasswordChangeService(**deps)

    def command(self,before=b'Current password',after=b'New password'):
        return ChangePassword(b't'*32,b'c'*32,uuid4(),PasswordChangeProof(bytearray(before),bytearray(after)))

    def test_invalid_passwords_and_key_never_enter_uow_and_erase(self):
        for before,after,key in ((b'',b'new',str(uuid4())),(b'old',b'\x00',str(uuid4())),
            (b'old',b'\xff',str(uuid4())),(b'old',b'x'*1025,str(uuid4())),(b'old',b'new','short')):
            service=self.service();command=self.command(before,after)
            with self.assertRaises(PasswordChangeError) as caught:service.change(command,idempotency_key=key)
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED')
            self.assertFalse(self.entered)
            self.assertFalse(any(command.passwords.current_password));self.assertFalse(any(command.passwords.new_password))

    def test_lock_failure_and_unknown_exception_fail_closed_erase(self):
        for outcome in (False,1,RuntimeError('Synthetic private data')):
            access=Mock()
            if isinstance(outcome,Exception):access.lock_deployment.side_effect=outcome
            else:access.lock_deployment.return_value=outcome
            command=self.command();service=self.service(access=access)
            with self.assertRaises(PasswordChangeError) as caught:service.change(command,idempotency_key=str(uuid4()))
            self.assertEqual(str(caught.exception),'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
            access.prove.assert_not_called()
            self.assertFalse(any(command.passwords.current_password));self.assertFalse(any(command.passwords.new_password))

    def test_missing_actor_denies_without_password_hashing(self):
        access=Mock();access.lock_deployment.return_value=True;access.prove.return_value=None
        hasher=Mock();service=self.service(access=access,hasher=hasher);command=self.command()
        with self.assertRaises(PasswordChangeError) as caught:service.change(command,idempotency_key=str(uuid4()))
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');hasher.hash_password.assert_not_called()
        self.assertFalse(any(command.passwords.current_password));self.assertFalse(any(command.passwords.new_password))

    def test_secrets_not_repr_or_static_error(self):
        command=self.command(b'Synthetic secret current',b'Synthetic secret new')
        self.assertNotIn('secret',repr(command))
        self.assertEqual(str(PasswordChangeError('Synthetic sensitive detail')),'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
