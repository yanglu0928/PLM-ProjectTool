import unittest
from unittest.mock import Mock, patch
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from plm_assistant.modules.auth.application.password_reset import ResetPassword, PasswordResetService, PasswordResetError
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof
from plm_assistant.modules.auth.application.password_reset_result import PasswordResetResult
from plm_assistant.modules.auth.application.user_state import UserStateActorProof
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class ResetHistoryTests(unittest.TestCase):
    def test_all_required_dependencies_reject_none(self):
        deps = dict(unit_of_work=self.owner._uow, access=self.access, repository=self.repo,
                    results=self.results, replay_verifier=self.replay, hasher=self.hasher,
                    audit=Mock(), receipts=self.receipts, license_guard=self.guard)
        for name in deps:
            with self.subTest(dependency=name):
                with self.assertRaises(ValueError): PasswordResetService(**(deps | {name: None}))

    def test_untrusted_history_coordinates_and_source_refuse_before_kdf(self):
        for fault in ('hint-type', 'hint-operation', 'hint-status', 'first-id', 'source-type', 'actor-type'):
            with self.subTest(fault=fault):
                self.setUp()
                if fault == 'hint-type': self.receipts.lookup_completed.return_value = object()
                elif fault == 'hint-operation': self.receipts.lookup_completed.return_value = IdempotencyResult('V1_AUTH_PASSWORD_CHANGE', self.first.result_id, 200)
                elif fault == 'hint-status': self.receipts.lookup_completed.return_value = IdempotencyResult(self.hint.ref_type, self.first.result_id, 201)
                elif fault == 'first-id': self.receipts.lookup_completed.return_value = IdempotencyResult(self.hint.ref_type, uuid4(), 200)
                elif fault == 'source-type': self.results.password_source.return_value = object()
                else: self.access.prove.return_value = object()
                with self.assertRaises(PasswordResetError) as caught: self.run_reset()
                self.assertEqual(caught.exception.code, 'AUTH_PASSWORD_RESET_UNAVAILABLE')
                self.hasher.hash_password.assert_not_called()
                self.results.verify_password_source.assert_not_called()
                self.access.lock_deployment.assert_not_called()
                self.receipts.reserve.assert_not_called(); self.repo.reset.assert_not_called()
                for tx in self.transactions: tx.commit.assert_not_called()
                self.assertFalse(any(self.command.password.temporary_password))
                self.assertEqual(self.active, [])

    def test_invalid_clock_refuses_without_kdf_or_write(self):
        for value in (None, True, 'not a time', datetime.now()):
            with self.subTest(value=type(value).__name__):
                self.setUp(); self.owner._clock = lambda: value
                with self.assertRaises(PasswordResetError): self.run_reset()
                self.access.prove.assert_not_called(); self.hasher.hash_password.assert_not_called()
                self.receipts.reserve.assert_not_called(); self.repo.reset.assert_not_called()
                for tx in self.transactions: tx.commit.assert_not_called()
                self.assertFalse(any(self.command.password.temporary_password))

    def setUp(self):
        now=datetime.now(timezone.utc);actor=uuid4();target=uuid4()
        self.proof=UserStateActorProof(UserReadView(actor,'Synthetic Admin','ENABLED','DEPLOYMENT_ADMIN',1,now,now,1),
            uuid4(),uuid4(),0,now,now+timedelta(hours=1),now+timedelta(hours=2))
        self.first=PasswordResetResult(uuid4(),target,actor,uuid4(),uuid4(),1,2,1,2,'ENABLED',uuid4(),uuid4(),0,now,now)
        self.hint=IdempotencyResult('V1_AUTH_USER_RESET_PASSWORD',self.first.result_id,200)
        self.source=PasswordHashResult('Synthetic hash','SCRYPT',{})
        self.command=ResetPassword(b't'*32,b'c'*32,uuid4(),target,1,True,PasswordResetProof(bytearray(b'Synthetic temporary')))
        self.active=[];self.events=[];self.transactions=[]
        @contextmanager
        def uow():
            tx=Mock();self.transactions.append(tx);self.active.append(tx);self.events.append('enter')
            try:yield tx
            finally:self.active.remove(tx);self.events.append('exit')
        self.access=Mock();self.access.prove.return_value=self.proof;self.access.lock_deployment.return_value=True
        self.receipts=Mock();self.receipts.lookup_completed.return_value=self.hint;self.receipts.reserve.return_value=self.hint
        self.results=Mock();self.results.get.return_value=self.first;self.results.password_source.return_value=self.source
        def verify(**kwargs):
            self.assertEqual(self.active,[]);self.events.append('verify');return True
        self.results.verify_password_source.side_effect=verify
        self.hasher=Mock();self.hasher.hash_password.return_value=self.source
        self.repo=Mock();self.replay=Mock();self.guard=Mock()
        self.owner=PasswordResetService(unit_of_work=uow,access=self.access,repository=self.repo,results=self.results,
            replay_verifier=self.replay,hasher=self.hasher,audit=Mock(),receipts=self.receipts,license_guard=self.guard)

    def run_reset(self):return self.owner.reset(self.command,idempotency_key=str(uuid4()))

    def test_history_verify_outside_then_fresh_source_final_no_hash_or_write(self):
        self.assertEqual(self.run_reset(),self.first)
        self.assertEqual(self.events,['enter','exit','verify','enter','exit'])
        self.results.require_password_source.assert_called_once()
        self.hasher.hash_password.assert_not_called();self.repo.reset.assert_not_called();self.replay.require_match.assert_not_called()
        self.assertEqual(self.access.prove.call_count,3)
        self.assertFalse(any(self.command.password.temporary_password))

    def test_false_nonbool_exception_no_write_and_release_erase(self):
        for value in (False,1,RuntimeError('Synthetic private')):
            self.setUp();self.results.verify_password_source.side_effect=None
            if isinstance(value,Exception):self.results.verify_password_source.side_effect=value
            else:self.results.verify_password_source.return_value=value
            slot=Mock();slot.acquire.return_value=True
            with patch('plm_assistant.modules.auth.application.password_reset._RESET_HASH_SLOTS',slot):
                with self.assertRaises(PasswordResetError) as caught:self.run_reset()
            self.assertEqual(caught.exception.code,'CONFLICT_IDEMPOTENCY' if value is False else 'AUTH_PASSWORD_RESET_UNAVAILABLE')
            slot.release.assert_called_once();self.receipts.reserve.assert_not_called()
            self.assertFalse(any(self.command.password.temporary_password))

    def test_race_exits_write_and_reprepares_once_before_history_kdf(self):
        self.receipts.lookup_completed.side_effect=[None,self.hint]
        self.assertEqual(self.run_reset(),self.first)
        self.assertEqual(self.events,['enter','exit','enter','exit','enter','exit','verify','enter','exit'])
        self.hasher.hash_password.assert_called_once();self.receipts.reserve.assert_called()
        self.assertEqual(self.receipts.reserve.call_count,2);self.repo.reset.assert_not_called()
        self.assertFalse(any(self.command.password.temporary_password))

    def test_repeated_race_is_bounded_and_no_lock_kdf(self):
        self.receipts.lookup_completed.return_value=None
        with self.assertRaises(PasswordResetError):self.run_reset()
        self.assertEqual(self.receipts.lookup_completed.call_count,2)
        self.assertEqual(self.receipts.reserve.call_count,2)
        self.results.verify_password_source.assert_not_called();self.repo.reset.assert_not_called()
        self.assertFalse(any(self.command.password.temporary_password))

    def test_current_actor_source_and_hint_rechecked_after_kdf(self):
        for failure in ('actor','source','hint','first'):
            self.setUp()
            if failure=='actor':self.access.prove.side_effect=[self.proof,None]
            elif failure=='source':self.results.require_password_source.side_effect=RuntimeError('Synthetic private')
            elif failure=='hint':self.receipts.reserve.return_value=IdempotencyResult(self.hint.ref_type,uuid4(),200)
            else:self.results.get.side_effect=[self.first,None]
            with self.assertRaises(PasswordResetError):self.run_reset()
            self.repo.reset.assert_not_called();self.assertFalse(any(self.command.password.temporary_password))
