from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4
from . import test_audit_worker_termination as fixture
from plm_assistant.modules.audit.infrastructure.export_retry_proof import SqlAlchemyAuditExportRetryProof
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError


class RetryEventProofTests(TestCase):
    def setUp(self):
        f=fixture.WorkerTerminationTests();f.setUp();self.accepted=f.f.accepted
        i=self.accepted.intent;self.identity=uuid4();self.started=self.accepted.accepted_at+timedelta(seconds=1);self.completed=self.started+timedelta(seconds=1)
        self.fields=dict(action='AUDIT_EXPORT_RETRY_SCHEDULED',trace_id=i.trace_id,event_scope=i.spec.scope,
            target_project_id=i.spec.project_id,actor_type='SYSTEM',actor_id=self.identity,original_actor_id=i.actor_id,
            actor_hint_digest=None,outcome='FAILED',target_version_id=None,reason_code='AUDIT_UNAVAILABLE',
            before_state='RUNNING',after_state='RETRY_WAIT',occurred_at=self.completed,audit_event_id=uuid4())
        self.session=Mock();self.owner=SqlAlchemyAuditExportRetryProof()

    def verify(self,rows,state='RETRY_WAIT'):
        self.session.scalars.return_value.all.return_value=rows
        with patch('plm_assistant.modules.audit.infrastructure.export_retry_proof._session',return_value=self.session):
            return self.owner.assert_retry(object(),accepted=self.accepted,identity=self.identity,state=state,
                started_at=self.started,completed_at=self.completed)

    def test_fixed_fields_and_attempt_window(self):
        row=SimpleNamespace(**self.fields);self.assertEqual(self.verify([row]),row.audit_event_id)
        wrong=dict(action='AUDIT_EXPORT_FAILED',trace_id=uuid4(),event_scope='PROJECT',target_project_id=uuid4(),
            actor_type='USER',actor_id=uuid4(),original_actor_id=uuid4(),actor_hint_digest='wrong',outcome='SUCCESS',
            target_version_id=uuid4(),reason_code='LICENSE_OPERATION_DENIED',before_state='CANCEL_REQUESTED',after_state='FAILED',
            occurred_at=self.completed+timedelta(seconds=1))
        for key,value in wrong.items():
            with self.subTest(field=key),self.assertRaises(AuditExportWorkerError):self.verify([SimpleNamespace(**(self.fields|{key:value}))])
        with self.assertRaises(AuditExportWorkerError):self.verify([SimpleNamespace(**(self.fields|{'occurred_at':self.started-timedelta(seconds=1)}))])

    def test_unique_terminal_event(self):
        row=SimpleNamespace(**(self.fields|{'action':'AUDIT_EXPORT_FAILED','after_state':'FAILED'}))
        self.assertEqual(self.verify([row],state='FAILED'),row.audit_event_id)
        for rows in ([],[row,row]):
            with self.assertRaises(AuditExportWorkerError):self.verify(rows,state='FAILED')
