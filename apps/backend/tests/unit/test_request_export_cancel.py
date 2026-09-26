from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_capture as fixture
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel,RequestAuditJobCancel,AuditExportCancelReceipt,AuditExportCancelRequestError
from plm_assistant.modules.audit.application.export_cancel_authorization import AuthorizedAuditExportCancel
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancelFacts,AuditExportCancellationResult,AuditExportCancellationError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint


class RequestCancelTests(TestCase):
    def setUp(self):
        f=fixture.WorkerCaptureTests();f.setUp();self.f=f
        self.c=RequestAuditExportCancel(f.intent.export_id,'DEPLOYMENT',None,b'a'*32,b'b'*32,uuid4(),'Synthetic reason')
        self.auth,self.cancel,self.receipts,self.sources,self.audit=Mock(),Mock(),Mock(),Mock(),Mock()
        self.proof=AuthorizedAuditExportCancel(f.intent.actor_id,'DEPLOYMENT',None,f.intent.actor_id,f.intent.intent_hash)
        self.auth.require_in_transaction.return_value=self.proof;self.receipts.reserve.return_value=None
        self.before=AuditExportCancelFacts(f.cmd.job_id,'RUNNING',None,None,None)
        self.after=AuditExportCancelFacts(f.cmd.job_id,'CANCEL_REQUESTED',f.intent.actor_id,datetime.now(timezone.utc),self.c.reason)
        self.cancel.read_facts.side_effect=[self.before,self.after]
        self.cancel.request_cancel.return_value=AuditExportCancellationResult(f.cmd.job_id,'CANCEL_REQUESTED',True)
        self.event=uuid4();self.audit.append.return_value=self.event
        self.result=AuditExportCancelReceipt(f.cmd.job_id,'CANCEL_REQUESTED',True,self.event)
        self.sources.receipt.return_value=self.result
        self.service=AuditExportCancelRequestService(unit_of_work=f.uow,repository=f.repo,authorization=self.auth,
            cancellations=self.cancel,receipts=self.receipts,sources=self.sources,audit=self.audit)
        self.key=str(uuid4())

    def test_root_actor_not_client_and_atomic_receipt(self):
        self.assertEqual(self.service.request(self.c,idempotency_key=self.key),self.result)
        auth=self.auth.require_in_transaction.call_args.kwargs['request']
        self.assertEqual((auth.original_actor_id,auth.spec),(self.f.intent.actor_id,self.f.intent.spec))
        self.f.tx.commit.assert_called_once();self.assertEqual(self.auth.require_in_transaction.call_count,2)
        event=self.audit.append.call_args.args[1]
        self.assertEqual(event.reason_code,'USER_REQUESTED');self.assertNotIn(self.c.reason,repr(event))

    def test_replay_no_cancel_audit_write_or_commit(self):
        self.cancel.read_facts.side_effect=[self.after]
        self.receipts.reserve.return_value=IdempotencyResult('V1_AUDIT_EXPORT_CANCEL',self.event,200)
        self.assertEqual(self.service.request(self.c,idempotency_key=self.key),self.result)
        self.cancel.request_cancel.assert_not_called();self.audit.append.assert_not_called();self.f.tx.commit.assert_not_called()

    def test_wrong_scope_before_authorization_and_invalid_reason_before_uow(self):
        with self.assertRaises(AuditExportCancelRequestError):self.service.request(replace(self.c,scope='PROJECT',project_id=uuid4()),idempotency_key=self.key)
        self.auth.require_in_transaction.assert_not_called()
        for reason in ('',True,'  invalid ','invalid\x00'):
            with self.assertRaises(AuditExportCancelRequestError):replace(self.c,reason=reason)
        self.cancel.request_cancel.assert_not_called()

    def test_postauth_denial_no_commit_and_invalid_receipt_rejects(self):
        self.auth.require_in_transaction.side_effect=[self.proof,replace(self.proof,actor_id=uuid4())]
        with self.assertRaises(AuditExportCancelRequestError):self.service.request(self.c,idempotency_key=self.key)
        self.f.tx.commit.assert_not_called()

    def test_cancel_facts_reject_partial_or_non_cancel_history_hide_reason(self):
        self.assertNotIn(self.c.reason,repr(self.after))
        for values in (dict(requested_by=None),dict(requested_at=None),dict(state='SUCCEEDED'),dict(reason='bad\x00')):
            with self.assertRaises(AuditExportCancellationError):replace(self.after,**values)

    def test_version_types_are_strict_and_bounded_before_any_ports(self):
        for version in (True,False,-1,2**63,'0',0.0):
            with self.assertRaises(AuditExportCancelRequestError):replace(self.c,expected_version=version)
            with self.assertRaises(AuditExportCancellationError):replace(self.before,lock_version=version)
        for version in (0,2**63-1):
            self.assertEqual(replace(self.c,expected_version=version).expected_version,version)
        self.auth.require_in_transaction.assert_not_called()

    def test_stale_new_command_never_cancels_audits_completes_or_commits(self):
        self.cancel.read_facts.side_effect=[replace(self.before,lock_version=2)]
        with self.assertRaises(AuditExportCancelRequestError) as caught:
            self.service.request(replace(self.c,expected_version=1),idempotency_key=self.key)
        self.assertEqual(caught.exception.code,'VERSION_CONFLICT')
        self.receipts.reserve.assert_called_once()
        self.cancel.request_cancel.assert_not_called();self.audit.append.assert_not_called()
        self.receipts.complete.assert_not_called();self.f.tx.commit.assert_not_called()

    def test_explicit_version_is_bound_to_original_operation_fingerprint(self):
        self.service.request(replace(self.c,expected_version=0),idempotency_key=self.key)
        args=self.receipts.reserve.call_args.kwargs
        self.assertEqual(args['scope'].operation,'V1_AUDIT_EXPORT_CANCEL_DEPLOYMENT')
        self.assertEqual(args['request_fingerprint'],canonical_payload_fingerprint(dict(
            export_id=str(self.c.export_id),intent_hash=self.f.intent.intent_hash,reason=self.c.reason,expected_version=0)))

    def test_legacy_fingerprint_is_unchanged(self):
        self.service.request(self.c,idempotency_key=self.key)
        self.assertEqual(self.receipts.reserve.call_args.kwargs['request_fingerprint'],canonical_payload_fingerprint(dict(
            export_id=str(self.c.export_id),intent_hash=self.f.intent.intent_hash,reason=self.c.reason)))

    def test_versioned_replay_after_version_changes_returns_original_no_writes(self):
        self.cancel.read_facts.side_effect=[replace(self.after,lock_version=3,state='CANCELLED')]
        self.receipts.reserve.return_value=IdempotencyResult('V1_AUDIT_EXPORT_CANCEL',self.event,200)
        self.assertEqual(self.service.request(replace(self.c,expected_version=0),idempotency_key=self.key),self.result)
        self.assertEqual(self.auth.require_in_transaction.call_count,2)
        self.cancel.request_cancel.assert_not_called();self.audit.append.assert_not_called()
        self.receipts.complete.assert_not_called();self.f.tx.commit.assert_not_called()

    def job_command(self,**values):
        command=RequestAuditJobCancel(self.f.cmd.job_id,self.c.scope,self.c.project_id,
            self.c.session_token,self.c.csrf_token,self.c.trace_id,self.c.reason,0)
        self.f.repo.peek_created_for_job.return_value=self.f.intent
        return replace(command,**values)

    def test_job_owner_resolves_real_root_in_same_uow_and_binds_fingerprint(self):
        self.assertEqual(self.service.request_job(self.job_command(),idempotency_key=self.key),self.result)
        self.f.repo.peek_created_for_job.assert_called_once_with(self.f.tx,job_id=self.f.cmd.job_id)
        self.f.repo.peek_created.assert_not_called()
        self.assertEqual(self.receipts.reserve.call_args.kwargs['request_fingerprint'],canonical_payload_fingerprint(dict(
            export_id=str(self.f.intent.export_id),intent_hash=self.f.intent.intent_hash,reason=self.c.reason,expected_version=0)))
        self.f.tx.commit.assert_called_once()

    def test_job_owner_requires_explicit_version_and_does_not_accept_export_command(self):
        for version in (None,True,-1,2**63):
            with self.assertRaises(AuditExportCancelRequestError):self.job_command(expected_version=version)
        with self.assertRaises(AuditExportCancelRequestError):self.service.request_job(self.c,idempotency_key=self.key)
        with self.assertRaises(AuditExportCancelRequestError):self.service.request(self.job_command(),idempotency_key=self.key)
        self.auth.require_in_transaction.assert_not_called()

    def test_job_owner_missing_hint_does_not_authorize_or_write(self):
        command=self.job_command();self.f.repo.peek_created_for_job.return_value=None
        with self.assertRaises(AuditExportCancelRequestError) as caught:self.service.request_job(command,idempotency_key=self.key)
        self.assertEqual(caught.exception.code,'RESOURCE_NOT_FOUND')
        self.auth.require_in_transaction.assert_not_called();self.cancel.read_facts.assert_not_called()
        self.f.tx.commit.assert_not_called()

    def test_job_owner_wrong_accepted_job_rejects_before_cancel_or_receipt(self):
        command=self.job_command(job_id=uuid4())
        with self.assertRaises(AuditExportCancelRequestError):self.service.request_job(command,idempotency_key=self.key)
        self.auth.require_in_transaction.assert_called_once()
        self.cancel.read_facts.assert_not_called();self.receipts.reserve.assert_not_called()
        self.f.tx.commit.assert_not_called()

    def test_job_owner_stale_version_replay_remains_authorized_and_immutable(self):
        command=self.job_command()
        self.cancel.read_facts.side_effect=[replace(self.after,state='CANCELLED',lock_version=3)]
        self.receipts.reserve.return_value=IdempotencyResult('V1_AUDIT_EXPORT_CANCEL',self.event,200)
        self.assertEqual(self.service.request_job(command,idempotency_key=self.key),self.result)
        self.assertEqual(self.auth.require_in_transaction.call_count,2)
        self.cancel.request_cancel.assert_not_called();self.f.tx.commit.assert_not_called()
