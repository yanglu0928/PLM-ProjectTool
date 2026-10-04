from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.cancel_request import RequestProjectJobCancel,JobCancelResult,JobCancelError,ProjectJobCancellation
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts
from plm_assistant.modules.audit.application.job_cancel_adapter import AuditJobCancelOwner
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelReceipt,AuditExportCancelRequestError
from plm_assistant.modules.auth.application.session_service import SessionError

class JobCancellationTests(TestCase):
    def setUp(self):
        self.c=RequestProjectJobCancel(uuid4(),uuid4(),b'a'*32,b'b'*32,uuid4(),'Synthetic cancellation',0)
        self.repo,self.sessions,self.guard,self.owner=Mock(),Mock(),Mock(),Mock()
        self.facts=JobReadFacts(self.c.job_id,'audit','AUDIT_EXPORT','PROJECT',self.c.project_id,uuid4(),'PENDING',0,datetime.now(timezone.utc),None)
        self.repo.get.return_value=self.facts
        self.result=JobCancelResult(self.c.job_id,'CANCELLED',True,2)
        self.active=False
        @contextmanager
        def uow():
            self.active=True
            try:yield Mock()
            finally:self.active=False
        def cancel(*args,**kwargs):
            self.assertFalse(self.active);return self.result
        self.owner.cancel.side_effect=cancel
        self.service=ProjectJobCancellation(unit_of_work=uow,repository=self.repo,sessions=self.sessions,license_guard=self.guard,owners={('audit','AUDIT_EXPORT'):self.owner})
        self.key=str(uuid4())
    def test_dispatch_ends_hint_transaction_and_passes_original_command(self):
        self.assertEqual(self.service.cancel(self.c,idempotency_key=self.key),self.result)
        self.sessions.validate.assert_called_once_with(self.c.session_token,csrf_token=self.c.csrf_token,require_csrf=True)
        self.owner.cancel.assert_called_once_with(self.c,idempotency_key=self.key)
    def test_unregistered_owner_wrong_scope_or_project_never_dispatches(self):
        for facts in (None,replace(self.facts,owner_module='unknown'),replace(self.facts,project_id=uuid4()),replace(self.facts,scope='GLOBAL',project_id=None)):
            self.repo.get.return_value=facts
            with self.assertRaises(JobCancelError):self.service.cancel(self.c,idempotency_key=self.key)
        self.owner.cancel.assert_not_called()
    def test_current_session_failure_before_hints_safe_codes(self):
        for code,expected in (('AUTH_ACCESS_DENIED','AUTH_CSRF_INVALID'),('AUTH_SESSION_EXPIRED','AUTH_SESSION_EXPIRED'),('SYSTEM_UNAVAILABLE','JOB_UNAVAILABLE')):
            self.sessions.validate.side_effect=SessionError(code)
            with self.assertRaises(JobCancelError) as caught:self.service.cancel(self.c,idempotency_key=self.key)
            self.assertEqual(caught.exception.code,expected)
        self.repo.get.assert_not_called();self.owner.cancel.assert_not_called()
    def test_strict_command_before_dependencies_and_no_reason_repr(self):
        self.assertNotIn(self.c.reason,repr(self.c))
        for field,value in (('expected_version',None),('expected_version',True),('expected_version',-1),('reason','bad\x00'),('reason',' untrimmed ')):
            with self.assertRaises(JobCancelError):replace(self.c,**{field:value})
        self.guard.require_valid.assert_not_called()
    def test_audit_adapter_binds_actual_receipt_and_refuses_unknown_version(self):
        requests=Mock();owner=AuditJobCancelOwner(requests=requests)
        receipt=AuditExportCancelReceipt(self.c.job_id,'CANCELLED',True,uuid4(),2)
        requests.request_job.return_value=receipt
        self.assertEqual(owner.cancel(self.c,idempotency_key=self.key),self.result)
        command=requests.request_job.call_args.args[0]
        self.assertEqual((command.job_id,command.scope,command.project_id,command.expected_version),(self.c.job_id,'PROJECT',self.c.project_id,0))
        for changed in (replace(receipt,lock_version=None),replace(receipt,job_id=uuid4())):
            requests.request_job.return_value=changed
            with self.assertRaises(JobCancelError):owner.cancel(self.c,idempotency_key=self.key)
        requests.request_job.side_effect=AuditExportCancelRequestError('VERSION_CONFLICT')
        with self.assertRaises(JobCancelError) as caught:owner.cancel(self.c,idempotency_key=self.key)
        self.assertEqual(caught.exception.code,'CONFLICT_VERSION')
