from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import ClaimedJob,JobLeaseError


class AuditJobCompletionTests(TestCase):
    def test_dependencies_required(self):
        with self.assertRaises(ValueError):AuditExportJobCompletion(queue=None,leases=Mock())
        with self.assertRaises(ValueError):AuditExportJobCompletion(queue=Mock(),leases=None)

    def setUp(self):
        self.request=AuditExportJobRequest(uuid4(),uuid4(),'DEPLOYMENT',None,uuid4())
        self.refs=AuditExportJobRef(uuid4(),uuid4())
        self.claim=ClaimedJob(self.refs.job_id,'AUDIT_EXPORT','DEPLOYMENT',None,dict(export_id=str(self.request.export_id),policy_version=self.request.policy_version),str(self.request.trace_id),1,1)
        self.queue,self.leases=Mock(),Mock();self.queue.find_export.return_value=self.refs
        self.leases.check_current.return_value=self.leases.finish.return_value=self.claim
        self.service=AuditExportJobCompletion(queue=self.queue,leases=self.leases)
        self.args=dict(request=self.request,refs=self.refs,fencing_token=1,worker_ref='worker')

    def test_exact_pair_and_checkpoint_then_finish_no_commit(self):
        tx=Mock();self.assertEqual(self.service.complete_current(tx,**self.args),self.claim)
        self.queue.find_export.assert_called_once_with(tx,request=self.request)
        self.leases.check_current.assert_called_once_with(tx,job_id=self.refs.job_id,fencing_token=1,worker_ref='worker')
        self.leases.finish.assert_called_once_with(tx,job_id=self.refs.job_id,fencing_token=1,worker_ref='worker')
        tx.commit.assert_not_called()

    def test_validation_before_port_calls_and_nested_recheck(self):
        for changes in (dict(request=True),dict(refs=True),dict(fencing_token=True),dict(worker_ref='../unsafe')):
            with self.assertRaises(JobLeaseError) as caught:self.service.complete_current(None,**(self.args|changes))
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED')
        object.__setattr__(self.request,'scope','GLOBAL')
        with self.assertRaises(JobLeaseError):self.service.complete_current(None,**self.args)
        self.queue.find_export.assert_not_called();self.leases.finish.assert_not_called()

    def test_mismatched_pair_never_finishes(self):
        for value in (None,True,AuditExportJobRef(uuid4(),self.refs.event_id)):
            self.queue.find_export.return_value=value
            with self.assertRaises(JobLeaseError):self.service.complete_current(None,**self.args)
        self.leases.check_current.assert_not_called();self.leases.finish.assert_not_called()

    def test_actual_claim_binding_before_mutation(self):
        for changes in (dict(job_id=uuid4()),dict(job_type='PARSE'),dict(scope='PROJECT'),dict(trace_id=str(uuid4())),dict(payload_refs={}),dict(fencing_token=True),dict(attempt_no=True),dict(attempt_no=0)):
            self.leases.check_current.return_value=replace(self.claim,**changes)
            with self.assertRaises(JobLeaseError):self.service.complete_current(None,**self.args)
        self.leases.finish.assert_not_called()

    def test_changed_return_rejected_caller_must_roll_back(self):
        self.leases.finish.return_value=replace(self.claim,attempt_no=2)
        with self.assertRaises(JobLeaseError):self.service.complete_current(None,**self.args)

    def test_stale_and_unknown_errors_no_retry_or_detail(self):
        self.leases.check_current.side_effect=JobLeaseError('STALE_LEASE')
        with self.assertRaises(JobLeaseError) as caught:self.service.complete_current(None,**self.args)
        self.assertEqual(caught.exception.code,'STALE_LEASE')
        self.leases.check_current.side_effect=RuntimeError('unsafe internal detail')
        with self.assertRaises(JobLeaseError) as caught:self.service.complete_current(None,**self.args)
        self.assertEqual(str(caught.exception),'JOB_STORE_UNAVAILABLE')
        self.leases.finish.assert_not_called()
