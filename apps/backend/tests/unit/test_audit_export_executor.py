from dataclasses import replace
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_termination as fixture
from . import test_audit_export_content as content_fixture
from plm_assistant.modules.audit.application.execute_export import AuditExportExecutor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.application.verify_termination import VerifiedAuditExportTermination
from plm_assistant.modules.audit.application.verify_cancel import VerifiedAuditExportCancellation
from plm_assistant.modules.audit.application.verify_retry import VerifiedAuditExportRetry
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellationResult
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionFacts
from plm_assistant.modules.jobs.application.retry_proof import RetryTransitionProof


class ExportExecutorTests(TestCase):
    def setUp(self):
        f=fixture.WorkerTerminationTests();f.setUp();self.command=f.f.cmd;self.claim=f.f.claim
        self.supervisor=f.supervisor;self.actor=f.actor
        names=('runner','reader','termination','termination_verifier','cancellation','cancellation_verifier','retry','retry_verifier')
        self.deps={name:Mock() for name in names}
        for dep in self.deps.values():dep._supervisor=self.supervisor;dep._actor=self.actor
        self.facts=AuditExportExecutionFacts(self.claim,1,'RUNNING','ACTIVE',True,None)
        self.deps['reader'].read.return_value=self.facts
        content=content_fixture.AuditExportContentTests();content.setUp()
        self.result=replace(content.source.result,export_id=self.command.export_id)
        self.deps['runner'].run.return_value=self.result
        self.term=VerifiedAuditExportTermination(AuditExportFailureResult(self.claim,'FAILED'),uuid4())
        self.cancel=VerifiedAuditExportCancellation(AuditExportCancellationResult(self.command.job_id,'CANCELLED',True),uuid4(),uuid4(),False)
        now=datetime.now(timezone.utc)
        self.retry=VerifiedAuditExportRetry(RetryTransitionProof(self.claim,'RETRY_WAIT',now-timedelta(seconds=1),now,now+timedelta(seconds=5)),uuid4())
        self.deps['termination_verifier'].verify.return_value=self.term
        self.deps['cancellation_verifier'].verify.return_value=self.cancel
        self.deps['retry_verifier'].verify.return_value=self.retry
        self.owner=AuditExportExecutor(supervisor=self.supervisor,**self.deps)

    def no_mutation(self):
        self.deps['termination'].terminate.assert_not_called();self.deps['retry'].retry.assert_not_called()
        self.deps['cancellation'].acknowledge.assert_not_called();self.deps['cancellation'].recover_expired.assert_not_called()

    def test_new_success_and_already_success_no_safety_writes(self):
        self.assertEqual(self.owner.execute(self.command).kind,'SUCCEEDED');self.no_mutation()
        self.deps['reader'].read.return_value=replace(self.facts,state='SUCCEEDED',lease_state='RELEASED',lease_alive=False)
        self.assertEqual(self.owner.execute(self.command).value,self.result);self.no_mutation()

    def test_actual_success_after_error_does_not_fail_or_retry(self):
        self.deps['reader'].read.side_effect=[self.facts,replace(self.facts,state='SUCCEEDED',lease_state='RELEASED',lease_alive=False)]
        self.deps['runner'].run.side_effect=[AuditExportWorkerError('STALE_LEASE'),self.result]
        self.assertEqual(self.owner.execute(self.command).kind,'SUCCEEDED');self.no_mutation()

    def test_success_then_revocation_never_rewrites_success(self):
        self.deps['reader'].read.side_effect=[self.facts,replace(self.facts,state='SUCCEEDED',lease_state='RELEASED',lease_alive=False)]
        self.deps['runner'].run.side_effect=AuditExportWorkerError('AUTH_ACCESS_DENIED')
        with self.assertRaises(AuditExportWorkerError):self.owner.execute(self.command)
        self.no_mutation()

    def test_retry_authority_denial_only_terminates_still_running(self):
        self.deps['runner'].run.side_effect=AuditExportWorkerError()
        self.deps['retry'].retry.side_effect=AuditExportWorkerError('LICENSE_OPERATION_DENIED')
        self.deps['retry_verifier'].verify.side_effect=AuditExportWorkerError('LICENSE_OPERATION_DENIED')
        self.assertEqual(self.owner.execute(self.command).kind,'FAILED')
        self.deps['termination'].terminate.assert_called_once_with(self.command,reason_code='LICENSE_OPERATION_DENIED')

    def test_terminal_denial_and_lost_ack_use_verified_failure(self):
        self.deps['runner'].run.side_effect=AuditExportWorkerError('AUTH_ACCESS_DENIED')
        self.deps['termination'].terminate.side_effect=AuditExportWorkerError()
        self.assertEqual(self.owner.execute(self.command).value,self.term)
        self.deps['termination'].terminate.assert_called_once_with(self.command,reason_code='AUTH_ACCESS_DENIED')
        self.deps['retry'].retry.assert_not_called()

    def test_transient_error_and_lost_ack_use_verified_retry(self):
        self.deps['runner'].run.side_effect=AuditExportWorkerError()
        self.deps['retry'].retry.side_effect=AuditExportWorkerError()
        self.assertEqual(self.owner.execute(self.command).kind,'RETRY_SCHEDULED')
        self.deps['retry'].retry.assert_called_once();self.deps['termination'].terminate.assert_not_called()

    def test_cancel_priority_after_run_failure(self):
        self.deps['reader'].read.side_effect=[self.facts,replace(self.facts,state='CANCEL_REQUESTED')]
        self.deps['runner'].run.side_effect=AuditExportWorkerError()
        self.assertEqual(self.owner.execute(self.command).kind,'CANCELLED')
        self.deps['cancellation'].acknowledge.assert_called_once();self.deps['retry'].retry.assert_not_called()

    def test_expiry_between_hint_and_ack_is_bounded(self):
        request=replace(self.facts,state='CANCEL_REQUESTED')
        self.deps['reader'].read.side_effect=[request,replace(request,lease_alive=False)]
        self.deps['cancellation'].acknowledge.side_effect=AuditExportWorkerError('STALE_LEASE')
        self.deps['cancellation_verifier'].verify.side_effect=[AuditExportWorkerError(),replace(self.cancel,expired=True)]
        self.assertTrue(self.owner.execute(self.command).value.expired)
        self.deps['cancellation'].acknowledge.assert_called_once();self.deps['cancellation'].recover_expired.assert_called_once()

    def test_replayed_retry_and_historical_receipt_never_runs_business(self):
        for facts in (replace(self.facts,state='RETRY_WAIT',lease_state='RELEASED',lease_alive=False,error_code='AUDIT_UNAVAILABLE'),
                      replace(self.facts,state='CANCELLED',lease_state='RELEASED',lease_alive=False,error_code='AUDIT_UNAVAILABLE'),
                      replace(self.facts,current_fencing_token=2,lease_state='RELEASED',lease_alive=False,error_code='AUDIT_UNAVAILABLE')):
            self.deps['reader'].read.return_value=facts
            self.assertEqual(self.owner.execute(self.command).kind,'RETRY_SCHEDULED')
        self.deps['runner'].run.assert_not_called();self.no_mutation()

    def test_stop_timeout_no_second_read_or_transition(self):
        self.deps['runner'].run.side_effect=AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT')
        with self.assertRaises(AuditExportWorkerError):self.owner.execute(self.command)
        self.deps['reader'].read.assert_called_once();self.no_mutation()

    def test_missing_receipt_never_guesses_success(self):
        self.deps['reader'].read.return_value=replace(self.facts,state='CANCELLED',lease_state='RELEASED',lease_alive=False,error_code='JOB_CANCELLED')
        self.deps['cancellation_verifier'].verify.side_effect=AuditExportWorkerError()
        with self.assertRaises(AuditExportWorkerError):self.owner.execute(self.command)
        self.no_mutation()

    def test_invalid_and_unknown_error_never_transitions(self):
        with self.assertRaises(AuditExportWorkerError):self.owner.execute(True)
        self.deps['reader'].read.assert_not_called()
        self.deps['runner'].run.side_effect=AuditExportWorkerError('AUDIT_HEARTBEAT_CAPACITY')
        with self.assertRaises(AuditExportWorkerError):self.owner.execute(self.command)
        self.no_mutation()

    def test_mismatched_supervisor_rejected(self):
        self.deps['retry']._supervisor=object()
        with self.assertRaises(ValueError):AuditExportExecutor(supervisor=self.supervisor,**self.deps)
