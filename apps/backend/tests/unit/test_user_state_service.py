import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_state import (
    UserStateService,ChangeUserState,UserStateActorProof,UserStateError)
from plm_assistant.modules.auth.application.user_state_result import UserStateResult
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class UserStateServiceTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc);self.actor=uuid4();self.user=uuid4()
        self.cmd=ChangeUserState(b't'*32,b'c'*32,uuid4(),self.user,1)
        actor=UserReadView(self.actor,'Synthetic Admin','ENABLED','DEPLOYMENT_ADMIN',1,now,now,1)
        self.proof=UserStateActorProof(actor,uuid4(),uuid4(),0,now-timedelta(minutes=1),
            now+timedelta(minutes=30),now+timedelta(hours=8))
        self.view=UserReadView(self.user,'Synthetic target','DISABLED','NONE',1,now,now,2)
        self.event=uuid4()
        self.result=UserStateResult(uuid4(),self.view,self.actor,self.event,self.cmd.trace_id,'DISABLE',1,2,now)
        self.tx=SimpleNamespace(commit=Mock())
        @contextmanager
        def uow():yield self.tx
        self.access=Mock();self.access.lock_deployment.return_value=True;self.access.prove.return_value=self.proof
        self.repo=Mock();self.repo.change.return_value=(self.view,'ENABLED',2)
        self.results=Mock();self.results.record.return_value=self.result;self.results.get.return_value=self.result
        self.audit=Mock();self.audit.append.return_value=self.event
        self.receipts=Mock();self.receipts.reserve.return_value=None
        self.guard=Mock()
        self.service=UserStateService(unit_of_work=uow,access=self.access,repository=self.repo,
            results=self.results,audit=self.audit,receipts=self.receipts,license_guard=self.guard)
    def test_atomic_success_current_final_audit(self):
        self.assertEqual(self.service.disable(self.cmd,idempotency_key='Synthetic-key-123'),self.result)
        self.tx.commit.assert_called_once();self.assertEqual(self.access.prove.call_count,2)
        self.assertEqual(self.guard.require_valid.call_count,2)
        draft=self.audit.append.call_args.args[1]
        self.assertEqual((draft.action,draft.before_state,draft.after_state),('USER_DISABLED','ENABLED','DISABLED'))
        self.assertNotIn(self.view.username_display,repr(draft))
    def test_enable_success_zero_count(self):
        view=replace(self.view,account_state='ENABLED')
        result=replace(self.result,first_view=view,operation='ENABLE',revoked_session_count=0)
        self.repo.change.return_value=(view,'DISABLED',0);self.results.record.return_value=result
        self.assertEqual(self.service.enable(self.cmd,idempotency_key='Synthetic-key-123'),result)
    def test_replay_current_proof_no_writes_commit(self):
        self.receipts.reserve.return_value=IdempotencyResult('V1_AUTH_USER_DISABLE',self.result.result_id,200)
        self.assertEqual(self.service.disable(self.cmd,idempotency_key='Synthetic-key-123'),self.result)
        self.repo.change.assert_not_called();self.results.record.assert_not_called()
        self.audit.append.assert_not_called();self.tx.commit.assert_not_called()
    def test_validation_before_dependencies(self):
        for change in (dict(expected_version=True),dict(expected_version=-1),dict(expected_version=2**63-1),
            dict(session_token=b'x'),dict(csrf_token='x'),dict(user_id='wrong')):
            with self.assertRaises(UserStateError) as caught:self.service.disable(replace(self.cmd,**change),idempotency_key='Synthetic-key-123')
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED')
        self.guard.require_valid.assert_not_called()
    def test_lost_or_changed_current_authority_no_commit(self):
        self.access.prove.side_effect=[self.proof,None]
        with self.assertRaises(UserStateError) as caught:self.service.disable(self.cmd,idempotency_key='Synthetic-key-123')
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');self.tx.commit.assert_not_called()
    def test_self_disable_requires_exact_true_special_check(self):
        cmd=replace(self.cmd,user_id=self.actor)
        view=replace(self.view,user_id=self.actor,deployment_role='DEPLOYMENT_ADMIN')
        result=replace(self.result,first_view=view)
        self.repo.change.return_value=(view,'ENABLED',2);self.results.record.return_value=result
        for value in (False,1,None):
            self.access.require_self_disabled.return_value=value
            with self.assertRaises(UserStateError):self.service.disable(cmd,idempotency_key='Synthetic-key-123')
        self.tx.commit.assert_not_called()
        self.access.require_self_disabled.return_value=True
        self.assertEqual(self.service.disable(cmd,idempotency_key='Synthetic-key-123'),result)
        self.tx.commit.assert_called_once()
    def test_bad_results_or_receipt_never_commit(self):
        for result in (None,replace(self.result,actor_id=uuid4()),replace(self.result,trace_id=uuid4()),
                       replace(self.result,revoked_session_count=3)):
            self.results.record.return_value=result
            with self.assertRaises(UserStateError):self.service.disable(self.cmd,idempotency_key='Synthetic-key-123')
        self.tx.commit.assert_not_called()
        self.receipts.reserve.return_value=IdempotencyResult('V1_AUTH_USER_ENABLE',self.result.result_id,200)
        with self.assertRaises(UserStateError):self.service.disable(self.cmd,idempotency_key='Synthetic-key-123')
    def test_bad_dependency_or_lock_is_static(self):
        self.access.lock_deployment.return_value=1
        with self.assertRaises(UserStateError) as caught:self.service.disable(self.cmd,idempotency_key='Synthetic-key-123')
        self.assertEqual(str(caught.exception),'AUTH_STATE_UNAVAILABLE')
        self.assertEqual(str(UserStateError('private source')),'AUTH_STATE_UNAVAILABLE')
