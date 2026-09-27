import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Event,Lock
from uuid import uuid4
from plm_assistant.modules.auth.application.password_reset import ResetPassword,PasswordResetService,PasswordResetError
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_state import UserStateActorProof
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult


class PasswordResetServiceTests(unittest.TestCase):
    def actor(self):
        now=datetime.now(timezone.utc)
        return UserStateActorProof(UserReadView(uuid4(),'Synthetic Admin','ENABLED','DEPLOYMENT_ADMIN',1,now,now,1),
            uuid4(),uuid4(),0,now,now+timedelta(hours=1),now+timedelta(hours=2))

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
            access=Mock();access.prove.return_value=self.actor()
            if isinstance(value,Exception):access.lock_deployment.side_effect=value
            else:access.lock_deployment.return_value=value
            hasher=Mock();hasher.hash_password.return_value=PasswordHashResult('Synthetic hash','SCRYPT',{})
            owner=self.owner(access=access,hasher=hasher);command=self.command()
            with self.assertRaises(PasswordResetError) as caught:owner.reset(command,idempotency_key=str(uuid4()))
            self.assertEqual(str(caught.exception),'AUTH_PASSWORD_RESET_UNAVAILABLE')
            self.assertEqual(access.prove.call_count,1);self.assertFalse(any(command.password.temporary_password))

    def test_hash_outside_preparation_and_global_lock_then_rechecks_actor(self):
        active=[];events=[]
        @contextmanager
        def uow():
            tx=Mock();active.append(tx);events.append('enter')
            try:yield tx
            finally:active.remove(tx);events.append('exit')
        access=Mock();access.prove.side_effect=[self.actor(),None]
        access.lock_deployment.side_effect=lambda tx:events.append('lock') or True
        def hash_password(password):
            self.assertEqual(active,[]);self.assertNotIn('lock',events);events.append('hash')
            return PasswordHashResult('Synthetic hash','SCRYPT',{})
        hasher=Mock();hasher.hash_password.side_effect=hash_password
        receipts=Mock();owner=self.owner(unit_of_work=uow,access=access,hasher=hasher,receipts=receipts)
        command=self.command()
        with self.assertRaises(PasswordResetError) as caught:owner.reset(command,idempotency_key=str(uuid4()))
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');receipts.reserve.assert_not_called()
        self.assertEqual(events,['enter','exit','hash','enter','lock','exit'])
        self.assertEqual(access.prove.call_count,2);self.assertFalse(any(command.password.temporary_password))

    def test_bad_preparation_proof_never_hashes_or_takes_global_lock(self):
        access=Mock();access.prove.return_value=Mock();hasher=Mock()
        owner=self.owner(access=access,hasher=hasher);command=self.command()
        with self.assertRaises(PasswordResetError):owner.reset(command,idempotency_key=str(uuid4()))
        access.lock_deployment.assert_not_called();hasher.hash_password.assert_not_called()
        self.assertFalse(any(command.password.temporary_password))

    def test_hash_failure_or_bad_output_releases_slot_never_enters_write(self):
        for value in (None,True,RuntimeError('Synthetic private hash failure')):
            access=Mock();access.prove.return_value=self.actor();hasher=Mock()
            if isinstance(value,Exception):hasher.hash_password.side_effect=value
            else:hasher.hash_password.return_value=value
            slot=Mock();slot.acquire.return_value=True
            owner=self.owner(access=access,hasher=hasher);command=self.command()
            with patch('plm_assistant.modules.auth.application.password_reset._RESET_HASH_SLOTS',slot):
                with self.assertRaises(PasswordResetError) as caught:owner.reset(command,idempotency_key=str(uuid4()))
            self.assertEqual(str(caught.exception),'AUTH_PASSWORD_RESET_UNAVAILABLE')
            slot.acquire.assert_called_once_with(timeout=5);slot.release.assert_called_once()
            access.lock_deployment.assert_not_called();self.assertFalse(any(command.password.temporary_password))

    def test_slot_timeout_does_not_hash_release_unowned_slot_or_write(self):
        access=Mock();access.prove.return_value=self.actor();hasher=Mock()
        slot=Mock();slot.acquire.return_value=False
        owner=self.owner(access=access,hasher=hasher);command=self.command()
        with patch('plm_assistant.modules.auth.application.password_reset._RESET_HASH_SLOTS',slot):
            with self.assertRaises(PasswordResetError):owner.reset(command,idempotency_key=str(uuid4()))
        slot.release.assert_not_called();hasher.hash_password.assert_not_called();access.lock_deployment.assert_not_called()
        self.assertFalse(any(command.password.temporary_password))

    def test_actual_process_gate_limits_five_preparations_to_four_active_hashes(self):
        gate=Event();four=Event();mutex=Lock();active=0;maximum=0;calls=0
        def hash_password(password):
            nonlocal active,maximum,calls
            with mutex:
                active+=1;calls+=1;maximum=max(maximum,active)
                if active==4:four.set()
            try:
                if not gate.wait(3):raise RuntimeError('Synthetic test deadline')
                return PasswordHashResult('Synthetic hash','SCRYPT',{})
            finally:
                with mutex:active-=1
        access=Mock();access.prove.side_effect=lambda *args,**kwargs:self.actor();access.lock_deployment.return_value=False
        hasher=Mock();hasher.hash_password.side_effect=hash_password
        owner=self.owner(access=access,hasher=hasher)
        def run():
            command=self.command()
            with self.assertRaises(PasswordResetError):owner.reset(command,idempotency_key=str(uuid4()))
            self.assertFalse(any(command.password.temporary_password))
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures=[pool.submit(run) for _ in range(5)]
            try:
                self.assertTrue(four.wait(2))
                with mutex:self.assertEqual((active,calls,maximum),(4,4,4))
            finally:gate.set()
            for future in futures:future.result(timeout=3)
        self.assertEqual((active,calls,maximum),(0,5,4))

    def test_missing_actor_denies_before_hash(self):
        access=Mock();access.lock_deployment.return_value=True;access.prove.return_value=None
        hasher=Mock();owner=self.owner(access=access,hasher=hasher);command=self.command()
        with self.assertRaises(PasswordResetError) as caught:owner.reset(command,idempotency_key=str(uuid4()))
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');hasher.hash_password.assert_not_called()
        self.assertFalse(any(command.password.temporary_password))

    def test_repr_and_error_never_echo_secret(self):
        self.assertNotIn('temporary password',repr(self.command()))
        self.assertEqual(str(PasswordResetError('Synthetic private password')),'AUTH_PASSWORD_RESET_UNAVAILABLE')
