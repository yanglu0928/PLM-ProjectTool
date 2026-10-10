import unittest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from dataclasses import replace
from unittest.mock import Mock
from plm_assistant.modules.audit.application.request_user_retry import AuditUserRetryService, RequestAuditUserRetry, AuditUserRetryError
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent, AcceptedAuditExport
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.export_submit_authorization import AuthorizedAuditExportSubmit, AuditExportSubmitAuthorizationError
from plm_assistant.modules.audit.application.user_retry_source import AuditUserRetrySource
from plm_assistant.modules.audit.application.retry_generation import AuditExportRetryGeneration
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobFailure
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult

class UserRetryCommandTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc);actor=uuid4();pid=uuid4()
        spec=AuditExportSpec('PROJECT',pid,'PROJECT_GOVERNANCE',now-timedelta(hours=1),now)
        old=AuditExportIntent(uuid4(),actor,uuid4(),now,spec,spec.fingerprint())
        self.accepted=AcceptedAuditExport(old,uuid4(),uuid4(),uuid4(),now)
        self.command=RequestAuditUserRetry(self.accepted.job_id,'PROJECT',pid,b's'*32,b'c'*32,uuid4(),3)
        self.fresh=AuditExportIntent(uuid4(),actor,self.command.trace_id,now+timedelta(seconds=6),spec,spec.fingerprint())
        self.new=AcceptedAuditExport(self.fresh,uuid4(),uuid4(),uuid4(),now+timedelta(seconds=7))
        self.source=AuditUserRetrySource(self.accepted,AuditUserRetryJobFailure(self.accepted.job_id,3,3,now,now+timedelta(seconds=5)),uuid4())
        self.result=AuditExportRetryGeneration(self.fresh.export_id,old.export_id,self.accepted.job_id,self.source.failure_event_id,
            self.new.job_id,self.new.event_id,uuid4(),3,0,now+timedelta(seconds=8))
        self.repo=Mock();self.repo.is_retryable_deadlock.return_value=False
        self.repo.peek_created_for_job.return_value=old
        self.repo.get_created.side_effect=lambda tx,export_id:old if export_id==old.export_id else self.fresh
        self.repo.get_accepted.side_effect=lambda tx,intent:self.accepted if intent==old else self.new
        self.repo.create_intent.return_value=self.fresh;self.repo.record_acceptance.return_value=self.new
        self.auth=Mock();self.auth.require_in_transaction.return_value=AuthorizedAuditExportSubmit(actor,'PROJECT',pid,spec.fingerprint())
        self.sources=Mock();self.sources.read.return_value=self.source
        self.generations=Mock();self.generations.record.return_value=self.result;self.generations.get.return_value=self.result
        self.receipts=Mock();self.receipts.reserve.return_value=None
        self.queue=Mock();self.queue.enqueue_export.return_value=AuditExportJobRef(self.new.job_id,self.new.event_id)
        self.queue.find_export.return_value=AuditExportJobRef(self.new.job_id,self.new.event_id)
        self.audit=Mock();self.audit.append.side_effect=[self.new.request_audit_event_id,self.result.retry_audit_event_id]
        self.txs=[]
        def uow():
            tx=Mock();tx.__enter__=Mock(return_value=tx);tx.__exit__=Mock(return_value=False)
            self.txs.append(tx);return tx
        self.service=AuditUserRetryService(unit_of_work=uow,repository=self.repo,authorization=self.auth,sources=self.sources,
            generations=self.generations,receipts=self.receipts,queue=self.queue,audit=self.audit)

    def run_command(self):return self.service.retry(self.command,idempotency_key='synthetic-user-retry-key-01')

    def test_atomic_first_response_and_final_authority(self):
        self.assertEqual(self.run_command(),self.result)
        self.assertEqual(self.auth.require_in_transaction.call_count,2)
        self.assertEqual(self.audit.append.call_count,2)
        self.txs[0].commit.assert_called_once()
        self.assertEqual(self.receipts.complete.call_args.kwargs['result'],IdempotencyResult('V1_AUDIT_USER_RETRY',self.fresh.export_id,202))

    def test_historical_replay_no_new_rows_or_commit(self):
        self.receipts.reserve.return_value=IdempotencyResult('V1_AUDIT_USER_RETRY',self.fresh.export_id,202)
        self.assertEqual(self.run_command(),self.result)
        self.repo.create_intent.assert_not_called();self.queue.enqueue_export.assert_not_called()
        self.audit.append.assert_not_called();self.receipts.complete.assert_not_called();self.generations.record.assert_not_called()
        self.txs[0].commit.assert_not_called()
        self.assertEqual(self.auth.require_in_transaction.call_count,2)

    def test_invalid_request_never_opens_uow(self):
        with self.assertRaises(AuditUserRetryError):self.service.retry(object(),idempotency_key='synthetic-user-retry-key-01')
        with self.assertRaises(AuditUserRetryError):self.service.retry(self.command,idempotency_key='short')
        with self.assertRaises(AuditUserRetryError):replace(self.command,expected_version=True)
        self.assertEqual(self.txs,[])

    def test_source_version_or_nonretryable_errors_preserved_no_create(self):
        for code in ('VERSION_CONFLICT','JOB_NOT_RETRYABLE'):
            self.sources.read.side_effect=JobLeaseError(code)
            with self.assertRaises(AuditUserRetryError) as caught:self.run_command()
            self.assertEqual(caught.exception.code,code)
        self.repo.create_intent.assert_not_called()
        for tx in self.txs:tx.commit.assert_not_called()

    def test_post_receipt_authority_loss_never_commits(self):
        proof=self.auth.require_in_transaction.return_value
        self.auth.require_in_transaction.side_effect=[proof,AuditExportSubmitAuthorizationError('LICENSE_OPERATION_DENIED')]
        with self.assertRaises(AuditUserRetryError) as caught:self.run_command()
        self.assertEqual(caught.exception.code,'LICENSE_OPERATION_DENIED')
        self.receipts.complete.assert_called_once();self.txs[0].commit.assert_not_called()

    def test_missing_replay_is_not_repaired_and_fault_text_hidden(self):
        self.receipts.reserve.return_value=IdempotencyResult('V1_AUDIT_USER_RETRY',self.fresh.export_id,202)
        self.generations.get.return_value=None
        with self.assertRaises(AuditUserRetryError):self.run_command()
        self.generations.get.side_effect=RuntimeError('private SQL or credentials')
        with self.assertRaises(AuditUserRetryError) as caught:self.run_command()
        self.assertNotIn('private',str(caught.exception))
        self.repo.create_intent.assert_not_called();self.txs[0].commit.assert_not_called()
