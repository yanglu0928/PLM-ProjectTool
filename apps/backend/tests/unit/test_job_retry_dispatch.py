from datetime import datetime,timezone
from uuid import uuid4
from unittest import TestCase
from unittest.mock import Mock
from dataclasses import replace
from plm_assistant.modules.jobs.application.retry_request import JobRetryRequests, RequestJobRetry, JobRetryResult, JobRetryError
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts,JobDetail,JobOwnerProjection,JobReadError
from plm_assistant.modules.auth.application.session_service import SessionError

class RetryDispatchTests(TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc);self.pid=uuid4();self.id=uuid4()
        self.c=RequestJobRetry(self.id,self.pid,b'a'*32,b'b'*32,uuid4(),3)
        self.facts=JobReadFacts(self.id,'audit','AUDIT_EXPORT','PROJECT',self.pid,uuid4(),'FAILED',3,self.now,self.now,3)
        self.reads,self.sessions,self.guard,self.owner=Mock(),Mock(),Mock(),Mock()
        self.reads.get.return_value=JobDetail(self.facts,JobOwnerProjection(self.id,False))
        self.result=JobRetryResult(self.id,uuid4(),self.pid,'PROJECT',self.now)
        self.owner.retry.return_value=self.result
        self.service=JobRetryRequests(reads=self.reads,sessions=self.sessions,license_guard=self.guard,owners={('audit','AUDIT_EXPORT'):self.owner})
    def invoke(self):return self.service.retry(self.c,idempotency_key='synthetic-valid-retry-key')

    def test_current_source_then_explicit_owner_not_retryable_hint(self):
        self.assertEqual(self.invoke(),self.result)
        self.guard.require_valid.assert_called_once();self.sessions.validate.assert_called_once()
        self.owner.retry.assert_called_once_with(self.c,idempotency_key='synthetic-valid-retry-key')

    def test_known_authorized_unsupported_owner_not_retryable(self):
        facts=replace(self.facts,owner_module='document',job_type='DOCUMENT_PARSE')
        self.reads.get.return_value=JobDetail(facts,JobOwnerProjection(self.id,False))
        with self.assertRaises(JobRetryError) as caught:self.invoke()
        self.assertEqual(caught.exception.code,'JOB_NOT_RETRYABLE');self.owner.retry.assert_not_called()

    def test_hidden_source_and_invalid_detail_do_not_dispatch(self):
        self.reads.get.side_effect=JobReadError('RESOURCE_NOT_FOUND')
        with self.assertRaises(JobRetryError) as caught:self.invoke()
        self.assertEqual(caught.exception.code,'RESOURCE_NOT_FOUND')
        self.reads.get.side_effect=None;self.reads.get.return_value=object()
        with self.assertRaises(JobRetryError):self.invoke()
        self.owner.retry.assert_not_called()

    def test_csrf_rejection_before_reads_and_owner(self):
        self.sessions.validate.side_effect=SessionError('AUTH_ACCESS_DENIED')
        with self.assertRaises(JobRetryError) as caught:self.invoke()
        self.assertEqual(caught.exception.code,'AUTH_CSRF_INVALID')
        self.reads.get.assert_not_called();self.owner.retry.assert_not_called()

    def test_wrong_owner_result_and_sensitive_fault_safe(self):
        self.owner.retry.return_value=replace(self.result,source_job_id=uuid4())
        with self.assertRaises(JobRetryError):self.invoke()
        self.owner.retry.side_effect=RuntimeError('private service key')
        with self.assertRaises(JobRetryError) as caught:self.invoke()
        self.assertNotIn('private',str(caught.exception))
