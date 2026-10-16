from dataclasses import replace
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import unittest
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent,AcceptedAuditExport,AuditExportSubmitService,AuditExportSubmitError
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.export_submit_authorization import AuditExportSubmitAuthorizationRequest,AuthorizedAuditExportSubmit
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.audit.infrastructure.export_submit_repository import SqlAlchemyAuditExportSubmitRepository


class SubmitExportTests(unittest.TestCase):
    def setUp(self):
        self.now,self.actor,self.project=datetime.now(timezone.utc),uuid4(),uuid4()
        self.spec=AuditExportSpec("PROJECT",self.project,"PROJECT_GOVERNANCE",self.now-timedelta(days=1),self.now)
        self.cmd=AuditExportSubmitAuthorizationRequest(b"s"*32,b"c"*32,uuid4(),self.spec)
        self.intent=AuditExportIntent(uuid4(),self.actor,self.cmd.trace_id,self.now,self.spec,self.spec.fingerprint())
        self.ref=AuditExportJobRef(uuid4(),uuid4());self.audit_id=uuid4()
        self.result=AcceptedAuditExport(self.intent,self.ref.job_id,self.ref.event_id,self.audit_id,self.now)
        self.auth,self.repo,self.receipts,self.queue,self.audit=Mock(),Mock(),Mock(),Mock(),Mock()
        self.auth.require_in_transaction.return_value=AuthorizedAuditExportSubmit(self.actor,"PROJECT",self.project,self.spec.fingerprint())
        self.repo.create_intent.return_value=self.intent;self.repo.get_created.return_value=self.intent
        self.repo.record_acceptance.return_value=self.result;self.repo.get_accepted.return_value=self.result
        self.repo.is_retryable_deadlock.side_effect=SqlAlchemyAuditExportSubmitRepository.is_retryable_deadlock
        self.receipts.reserve.return_value=None;self.queue.enqueue_export.return_value=self.ref;self.queue.find_export.return_value=self.ref
        self.audit.append.return_value=self.audit_id;self.txs=[]
        def uow():
            tx=Mock();tx.__enter__=Mock(return_value=tx);tx.__exit__=Mock(return_value=False);self.txs.append(tx);return tx
        self.service=AuditExportSubmitService(unit_of_work=uow,authorization=self.auth,repository=self.repo,receipts=self.receipts,queue=self.queue,audit=self.audit)

    def submit(self,cmd=None):return self.service.submit_idempotent(cmd or self.cmd,idempotency_key="synthetic-valid-key-01")

    def replay(self):self.receipts.reserve.return_value=IdempotencyResult("V1_AUDIT_EXPORT",self.intent.export_id,202)

    def test_first_atomic_wiring_safe_job_target_and_receipt(self):
        self.assertEqual(self.submit(),self.result)
        tx=self.txs[0];self.auth.require_in_transaction.assert_called_once_with(tx,request=self.cmd)
        scope=self.receipts.reserve.call_args.kwargs["scope"]
        self.assertEqual((scope.actor_id,scope.project_id,scope.operation),(self.actor,self.project,"V1_AUDIT_EXPORT_PROJECT_SUBMIT"))
        self.assertEqual(self.receipts.reserve.call_args.kwargs["request_fingerprint"],bytes.fromhex(self.spec.fingerprint()))
        event=self.audit.append.call_args.args[1]
        self.assertEqual((event.target_owner_module,event.target_object_type,event.target_object_id),("jobs","JOB-01",self.ref.job_id))
        self.assertEqual(event.reason_code,self.spec.purpose);self.assertIsNone(event.actor_hint_digest)
        self.assertEqual(self.receipts.complete.call_args.kwargs["result"],IdempotencyResult("V1_AUDIT_EXPORT",self.intent.export_id,202))
        tx.commit.assert_called_once()

    def test_replay_original_trace_and_refs_no_new_rows_commit(self):
        self.replay();new=replace(self.cmd,trace_id=uuid4())
        self.assertEqual(self.submit(new),self.result)
        self.assertEqual(self.queue.find_export.call_args.kwargs["request"].trace_id,self.intent.trace_id)
        self.repo.create_intent.assert_not_called();self.repo.record_acceptance.assert_not_called()
        self.queue.enqueue_export.assert_not_called();self.audit.append.assert_not_called()
        self.receipts.complete.assert_not_called();self.txs[0].commit.assert_not_called()

    def test_missing_or_replaced_original_result_rejected_not_repaired(self):
        self.replay()
        for ref in (None,AuditExportJobRef(uuid4(),uuid4())):
            self.queue.find_export.return_value=ref
            with self.assertRaises(AuditExportSubmitError):self.submit()
        self.queue.find_export.return_value=self.ref;self.repo.get_accepted.return_value=None
        with self.assertRaises(AuditExportSubmitError):self.submit()
        self.queue.enqueue_export.assert_not_called();self.repo.record_acceptance.assert_not_called()

    def test_invalid_before_authorization_or_uow(self):
        for cmd in (object(),replace(self.cmd,session_token=b"short"),replace(self.cmd,trace_id=True)):
            with self.assertRaises(AuditExportSubmitError):self.submit(cmd)
        self.assertEqual(self.txs,[]);self.auth.require_in_transaction.assert_not_called()

    def test_wrong_authority_or_intent_binding_fails(self):
        self.auth.require_in_transaction.return_value=True
        with self.assertRaises(AuditExportSubmitError):self.submit()
        self.receipts.reserve.assert_not_called()
        self.auth.require_in_transaction.return_value=AuthorizedAuditExportSubmit(self.actor,"PROJECT",self.project,self.spec.fingerprint())
        self.repo.create_intent.return_value=replace(self.intent,actor_id=uuid4())
        with self.assertRaises(AuditExportSubmitError):self.submit()
        self.queue.enqueue_export.assert_not_called()

    def test_safe_storage_failure_no_commit_no_generic_retry(self):
        self.receipts.complete.side_effect=RuntimeError("synthetic secret detail 40P01")
        with self.assertRaises(AuditExportSubmitError) as caught:self.submit()
        self.assertEqual(str(caught.exception),"AUDIT_UNAVAILABLE")
        self.assertEqual(len(self.txs),1);self.txs[0].commit.assert_not_called()

    def test_actual_type_deadlock_classifier_and_cycle(self):
        classify=SqlAlchemyAuditExportSubmitRepository.is_retryable_deadlock
        deadlock=DBAPIError("synthetic",{},SimpleNamespace(sqlstate="40P01"))
        wrapped=RuntimeError("safe");wrapped.__context__=deadlock
        self.assertTrue(classify(wrapped))
        self.assertFalse(classify(RuntimeError("40P01")))
        self.assertFalse(classify(DBAPIError("synthetic",{},SimpleNamespace(sqlstate="08006"))))
        self.assertFalse(classify("40P01"))
        cycle=RuntimeError("cycle");cycle.__context__=cycle;self.assertFalse(classify(cycle))

    def test_deadlock_whole_uow_retry_reauthorizes_and_exhausts_three(self):
        deadlock=DBAPIError("synthetic",{},SimpleNamespace(sqlstate="40P01"))
        self.repo.create_intent.side_effect=[deadlock,self.intent]
        self.assertEqual(self.submit(),self.result)
        self.assertEqual(len(self.txs),2);self.assertEqual(self.auth.require_in_transaction.call_count,2)
        self.txs[0].commit.assert_not_called();self.txs[1].commit.assert_called_once()
        self.txs=[];self.auth.reset_mock();self.repo.create_intent.side_effect=[deadlock]*3
        with self.assertRaises(AuditExportSubmitError):self.submit()
        self.assertEqual(len(self.txs),3);self.assertEqual(self.auth.require_in_transaction.call_count,3)
        for tx in self.txs:tx.commit.assert_not_called()
