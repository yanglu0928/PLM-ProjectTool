from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError


class AuditExportFailureTests(TestCase):
    def setUp(self):
        self.queue,self.leases,self.tx=Mock(),Mock(),Mock()
        self.request=AuditExportJobRequest(uuid4(),uuid4(),'DEPLOYMENT',None,uuid4())
        self.refs=AuditExportJobRef(uuid4(),uuid4())
        self.claim=ClaimedJob(self.refs.job_id,'AUDIT_EXPORT','DEPLOYMENT',None,
            dict(export_id=str(self.request.export_id),policy_version=self.request.policy_version),str(self.request.trace_id),1,1)
        self.queue.find_export.return_value=self.refs
        self.leases.check_current.return_value=self.claim
        self.leases.retry_or_fail.return_value='FAILED'
        self.service=AuditExportJobFailure(queue=self.queue,leases=self.leases)
        self.args=dict(request=self.request,refs=self.refs,fencing_token=1,worker_ref='worker',
            error_code='AUDIT_UNAVAILABLE',retryable=False)

    def test_same_transaction_never_commits(self):
        result=self.service.fail_current(self.tx,**self.args)
        self.assertEqual((result.claim,result.state),(self.claim,'FAILED'))
        self.leases.retry_or_fail.assert_called_once_with(self.tx,job_id=self.refs.job_id,
            fencing_token=1,worker_ref='worker',error_code='AUDIT_UNAVAILABLE',retryable=False,delay_seconds=0)
        self.tx.commit.assert_not_called()

    def test_validation_before_owned_ports(self):
        for field,values in (('error_code',('private path',True,None)),('retryable',(1,None,'yes')),
                            ('delay_seconds',(True,-1,86401,'0')),('fencing_token',(True,0)),('worker_ref',('',None))):
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaises(JobLeaseError) as cm:
                    self.service.fail_current(self.tx,**(self.args|{field:value}))
                self.assertEqual(cm.exception.code,'VALIDATION_FAILED')
        self.queue.find_export.assert_not_called()

    def test_pair_and_claim_mismatch_never_transitions(self):
        self.queue.find_export.return_value=AuditExportJobRef(uuid4(),uuid4())
        with self.assertRaises(JobLeaseError):self.service.fail_current(self.tx,**self.args)
        self.queue.find_export.return_value=self.refs
        for value in (replace(self.claim,scope='PROJECT'),replace(self.claim,payload_refs={}),replace(self.claim,attempt_no=4)):
            self.leases.check_current.return_value=value
            with self.assertRaises(JobLeaseError):self.service.fail_current(self.tx,**self.args)
        self.leases.retry_or_fail.assert_not_called()

    def test_stale_and_unexpected_errors_safe(self):
        for error,code in ((JobLeaseError('STALE_LEASE'),'STALE_LEASE'),(RuntimeError('private path'),'JOB_STORE_UNAVAILABLE')):
            self.leases.check_current.side_effect=error
            with self.assertRaises(JobLeaseError) as cm:self.service.fail_current(self.tx,**self.args)
            self.assertEqual(str(cm.exception),code)
        self.leases.retry_or_fail.assert_not_called()

    def test_retry_cap_and_repository_return(self):
        for attempt,expected in ((1,'RETRY_WAIT'),(2,'RETRY_WAIT'),(3,'FAILED')):
            self.leases.check_current.return_value=replace(self.claim,attempt_no=attempt)
            self.leases.retry_or_fail.return_value=expected
            self.assertEqual(self.service.fail_current(self.tx,**(self.args|{'retryable':True})).state,expected)
            self.leases.retry_or_fail.return_value='SUCCEEDED'
            with self.assertRaises(JobLeaseError):self.service.fail_current(self.tx,**(self.args|{'retryable':True}))
        self.tx.commit.assert_not_called()
