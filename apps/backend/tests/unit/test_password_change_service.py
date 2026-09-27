import unittest
from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event,Lock
from plm_assistant.modules.auth.application.password_change import ChangePassword,PasswordChangeService,PasswordChangeError
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeProof
from plm_assistant.modules.auth.application.password_change_actor import PasswordChangeActorProof
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult


class PasswordChangeServiceTests(unittest.TestCase):
    def actor(self):
        now=datetime.now(timezone.utc)
        return PasswordChangeActorProof(UserReadView(uuid4(),'Synthetic user','ENABLED','NONE',1,now,now,1),
            uuid4(),False,uuid4(),0,now,now+timedelta(hours=1),now+timedelta(hours=2))

    def access(self):
        access=Mock();access.prove.return_value=self.actor()
        access.current_password_source.return_value=PasswordHashResult('Synthetic source','SCRYPT',{})
        access.verify_password_source.return_value=False
        return access

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
            access=self.access()
            if isinstance(outcome,Exception):access.lock_deployment.side_effect=outcome
            else:access.lock_deployment.return_value=outcome
            command=self.command();service=self.service(access=access)
            with self.assertRaises(PasswordChangeError) as caught:service.change(command,idempotency_key=str(uuid4()))
            self.assertEqual(str(caught.exception),'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
            self.assertEqual(access.prove.call_count,1)
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

    def test_both_kdfs_outside_transactions_and_recheck_denies_without_receipt(self):
        active=[];events=[]
        @contextmanager
        def uow():
            tx=Mock();active.append(tx);events.append('enter')
            try:yield tx
            finally:active.remove(tx);events.append('exit')
        access=self.access();access.prove.side_effect=[self.actor(),None]
        def verify(**kwargs):self.assertEqual(active,[]);events.append('verify');return True
        def hash_password(password):self.assertEqual(active,[]);events.append('hash');return PasswordHashResult('Synthetic hash','SCRYPT',{})
        access.verify_password_source.side_effect=verify;access.lock_deployment.side_effect=lambda tx:events.append('lock') or True
        hasher=Mock();hasher.hash_password.side_effect=hash_password;receipts=Mock()
        command=self.command();service=self.service(unit_of_work=uow,access=access,hasher=hasher,receipts=receipts)
        with self.assertRaises(PasswordChangeError) as caught:service.change(command,idempotency_key=str(uuid4()))
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');receipts.reserve.assert_not_called()
        self.assertEqual(events,['enter','exit','verify','hash','enter','lock','exit'])

    def test_changed_credential_source_cannot_authorize_fresh_write(self):
        access=self.access();before=self.actor();access.prove.side_effect=[before,replace(before,credential_id=uuid4())]
        access.verify_password_source.return_value=True;access.lock_deployment.return_value=True
        hasher=Mock();hasher.hash_password.return_value=PasswordHashResult('Synthetic hash','SCRYPT',{})
        receipts=Mock();receipts.reserve.return_value=None;repository=Mock()
        command=self.command();service=self.service(access=access,hasher=hasher,receipts=receipts,repository=repository)
        with self.assertRaises(PasswordChangeError) as caught:service.change(command,idempotency_key=str(uuid4()))
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');repository.change.assert_not_called()

    def test_bad_source_or_truthy_verifier_never_reaches_global_lock(self):
        for source,matched in ((None,True),(True,True),(PasswordHashResult('Synthetic hash','SCRYPT',{}),1)):
            access=self.access();access.current_password_source.return_value=source;access.verify_password_source.return_value=matched
            command=self.command();service=self.service(access=access)
            with self.assertRaises(PasswordChangeError):service.change(command,idempotency_key=str(uuid4()))
            access.lock_deployment.assert_not_called()
            self.assertFalse(any(command.passwords.current_password));self.assertFalse(any(command.passwords.new_password))

    def test_slot_timeout_no_verification_or_hash_and_no_unowned_release(self):
        access=self.access();hasher=Mock();slot=Mock();slot.acquire.return_value=False
        command=self.command();service=self.service(access=access,hasher=hasher)
        with patch('plm_assistant.modules.auth.application.password_change._CHANGE_KDF_SLOTS',slot):
            with self.assertRaises(PasswordChangeError):service.change(command,idempotency_key=str(uuid4()))
        slot.acquire.assert_called_once_with(timeout=5);slot.release.assert_not_called()
        access.verify_password_source.assert_not_called();hasher.hash_password.assert_not_called()

    def test_verifier_failure_releases_slot_and_wipes_both(self):
        access=self.access();access.verify_password_source.side_effect=RuntimeError('Synthetic private verifier')
        command=self.command();service=self.service(access=access);slot=Mock();slot.acquire.return_value=True
        with patch('plm_assistant.modules.auth.application.password_change._CHANGE_KDF_SLOTS',slot):
            with self.assertRaises(PasswordChangeError) as caught:service.change(command,idempotency_key=str(uuid4()))
        self.assertEqual(str(caught.exception),'AUTH_PASSWORD_CHANGE_UNAVAILABLE');slot.release.assert_called_once()
        self.assertFalse(any(command.passwords.current_password));self.assertFalse(any(command.passwords.new_password))

    def test_bad_new_hash_releases_slot_without_global_write(self):
        for output in (None,True,RuntimeError('Synthetic private new hash')):
            access=self.access();access.verify_password_source.return_value=True;hasher=Mock()
            if isinstance(output,Exception):hasher.hash_password.side_effect=output
            else:hasher.hash_password.return_value=output
            command=self.command();service=self.service(access=access,hasher=hasher)
            slot=Mock();slot.acquire.return_value=True
            with patch('plm_assistant.modules.auth.application.password_change._CHANGE_KDF_SLOTS',slot):
                with self.assertRaises(PasswordChangeError):service.change(command,idempotency_key=str(uuid4()))
            slot.release.assert_called_once();access.lock_deployment.assert_not_called()
            self.assertFalse(any(command.passwords.current_password));self.assertFalse(any(command.passwords.new_password))

    def test_actual_gate_bounds_five_verifications_to_four(self):
        unblock=Event();four=Event();mutex=Lock();active=0;maximum=0;calls=0
        def verify(**kwargs):
            nonlocal active,maximum,calls
            with mutex:
                active+=1;calls+=1;maximum=max(maximum,active)
                if active==4:four.set()
            try:
                if not unblock.wait(3):raise RuntimeError('Synthetic test deadline')
                return False
            finally:
                with mutex:active-=1
        access=self.access();access.verify_password_source.side_effect=verify;access.lock_deployment.return_value=False
        service=self.service(access=access)
        def run():
            command=self.command()
            with self.assertRaises(PasswordChangeError):service.change(command,idempotency_key=str(uuid4()))
            self.assertFalse(any(command.passwords.current_password));self.assertFalse(any(command.passwords.new_password))
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures=[pool.submit(run) for _ in range(5)]
            try:
                self.assertTrue(four.wait(2))
                with mutex:self.assertEqual((active,calls,maximum),(4,4,4))
            finally:unblock.set()
            for future in futures:future.result(timeout=3)
        self.assertEqual((active,calls,maximum),(0,5,4))
