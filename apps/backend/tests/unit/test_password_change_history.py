import unittest
from unittest.mock import Mock
from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from plm_assistant.modules.auth.application.password_change import ChangePassword,PasswordChangeService,PasswordChangeError
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeProof
from plm_assistant.modules.auth.application.password_change_result import PasswordChangeResult
from plm_assistant.modules.auth.application.password_change_actor import PasswordChangeActorProof
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class ChangeHistoryTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc);actor=uuid4()
        self.proof=PasswordChangeActorProof(UserReadView(actor,'Synthetic user','ENABLED','NONE',3,now,now,3),
            uuid4(),False,uuid4(),0,now,now+timedelta(hours=1),now+timedelta(hours=2))
        self.first=PasswordChangeResult(uuid4(),actor,uuid4(),uuid4(),1,2,1,2,uuid4(),uuid4(),1,now,now)
        self.hint=IdempotencyResult('V1_AUTH_PASSWORD_CHANGE',self.first.result_id,200)
        self.source=PasswordHashResult('Synthetic source','SCRYPT',{})
        self.command=ChangePassword(b't'*32,b'c'*32,uuid4(),PasswordChangeProof(bytearray(b'Synthetic old'),bytearray(b'Synthetic new')))
        self.active=[];self.events=[]
        @contextmanager
        def uow():
            tx=Mock();self.active.append(tx);self.events.append('enter')
            try:yield tx
            finally:self.active.remove(tx);self.events.append('exit')
        self.access=Mock();self.access.prove.return_value=self.proof;self.access.lock_deployment.return_value=True
        self.access.current_password_source.return_value=self.source;self.access.verify_password_source.return_value=False
        self.receipts=Mock();self.receipts.lookup_completed.return_value=self.hint;self.receipts.reserve.return_value=self.hint
        self.results=Mock();self.results.get.return_value=self.first;self.results.password_source.return_value=self.source
        def verify(**kwargs):self.assertEqual(self.active,[]);self.events.append('verify');return True
        self.results.verify_password_source.side_effect=verify
        self.hasher=Mock();self.repo=Mock();self.replay=Mock()
        self.owner=PasswordChangeService(unit_of_work=uow,access=self.access,repository=self.repo,results=self.results,
            replay_verifier=self.replay,hasher=self.hasher,audit=Mock(),receipts=self.receipts)

    def run_change(self):return self.owner.change(self.command,idempotency_key=str(uuid4()))

    def erased(self):
        self.assertFalse(any(self.command.passwords.current_password))
        self.assertFalse(any(self.command.passwords.new_password))

    def test_two_history_kdfs_outside_then_two_fresh_sources_no_current_or_hash(self):
        self.assertEqual(self.run_change(),self.first)
        self.assertEqual(self.events,['enter','exit','verify','verify','enter','exit'])
        self.assertEqual([c.kwargs['role'] for c in self.results.require_password_source.call_args_list],['BEFORE','AFTER'])
        self.access.current_password_source.assert_not_called();self.access.verify_password_source.assert_not_called()
        self.hasher.hash_password.assert_not_called();self.repo.change.assert_not_called();self.replay.require_match.assert_not_called()
        self.erased()

    def test_each_historical_mismatch_or_nonbool_denies_before_write(self):
        for outcomes in ((False,),(True,False),(1,),(True,1),(RuntimeError('Synthetic private'),)):
            self.setUp();self.results.verify_password_source.side_effect=list(outcomes)
            with self.assertRaises(PasswordChangeError) as caught:self.run_change()
            self.assertEqual(caught.exception.code,'CONFLICT_IDEMPOTENCY' if False in outcomes else 'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
            self.receipts.reserve.assert_not_called();self.erased()

    def test_current_false_miss_race_reprepares_history_not_invalid_credentials(self):
        self.receipts.lookup_completed.side_effect=[None,self.hint]
        self.assertEqual(self.run_change(),self.first)
        self.assertEqual(self.receipts.reserve.call_count,2)
        self.access.verify_password_source.assert_called_once();self.hasher.hash_password.assert_not_called()
        self.assertEqual(self.events,['enter','exit','enter','exit','enter','exit','verify','verify','enter','exit'])
        self.repo.change.assert_not_called();self.erased()

    def test_repeated_miss_bounded(self):
        self.receipts.lookup_completed.return_value=None
        with self.assertRaises(PasswordChangeError):self.run_change()
        self.assertEqual(self.receipts.lookup_completed.call_count,2);self.assertEqual(self.receipts.reserve.call_count,2)
        self.results.verify_password_source.assert_not_called();self.repo.change.assert_not_called();self.erased()

    def test_current_identity_or_source_loss_after_kdf_never_writes(self):
        for where in ('actor','source','hint'):
            self.setUp()
            if where=='actor':self.access.prove.side_effect=[self.proof,None]
            elif where=='source':self.results.require_password_source.side_effect=RuntimeError('Synthetic private')
            else:self.receipts.reserve.return_value=IdempotencyResult(self.hint.ref_type,uuid4(),200)
            with self.assertRaises(PasswordChangeError):self.run_change()
            self.repo.change.assert_not_called();self.erased()
