from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4
from . import test_audit_worker_cancel as fixture
from plm_assistant.modules.audit.infrastructure.export_cancel_proof import SqlAlchemyAuditExportCancelProof
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError


class CancelCompletionProofTests(TestCase):
    def setUp(self):
        f=fixture.WorkerCancelTests();f.setUp();self.accepted=f.f.f.accepted
        i=self.accepted.intent;self.identity=uuid4();self.now=max(datetime.now(timezone.utc),self.accepted.accepted_at+timedelta(seconds=2))
        self.requested=self.now-timedelta(seconds=1)
        self.fields=dict(action='AUDIT_EXPORT_CANCELLED',trace_id=i.trace_id,event_scope=i.spec.scope,
            target_project_id=i.spec.project_id,actor_type='SYSTEM',actor_id=self.identity,original_actor_id=i.actor_id,
            actor_hint_digest=None,outcome='SUCCESS',target_version_id=None,reason_code='USER_REQUESTED',
            before_state='CANCEL_REQUESTED',after_state='CANCELLED',occurred_at=self.now,audit_event_id=uuid4())
        self.session=Mock();self.owner=SqlAlchemyAuditExportCancelProof()
        self.first_id=uuid4()
        self.session.scalar.return_value=SimpleNamespace(action='AUDIT_EXPORT_CANCEL_REQUESTED',target_object_id=self.accepted.job_id,
            target_owner_module='jobs',target_object_type='JOB-01',occurred_at=self.requested)

    def verify(self,rows,expired=False):
        self.session.scalars.return_value.all.return_value=rows
        with patch('plm_assistant.modules.audit.infrastructure.export_cancel_proof._session',return_value=self.session):
            return self.owner.assert_completion(object(),accepted=self.accepted,identity=self.identity,expired=expired,
                completed_at=self.now,requested_at=self.requested,first_request_event_id=self.first_id)

    def test_exact_fields_and_completion_window(self):
        row=SimpleNamespace(**self.fields)
        self.assertEqual(self.verify([row]),row.audit_event_id)
        wrong=dict(action='AUDIT_EXPORT_CANCEL_RECOVERED',trace_id=uuid4(),event_scope='PROJECT',
            target_project_id=uuid4(),actor_type='USER',actor_id=uuid4(),original_actor_id=uuid4(),
            actor_hint_digest='wrong',outcome='FAILED',target_version_id=uuid4(),reason_code='LEASE_EXPIRED',
            before_state='RUNNING',after_state='SUCCEEDED',occurred_at=self.now+timedelta(seconds=1))
        for key,value in wrong.items():
            with self.subTest(field=key),self.assertRaises(AuditExportWorkerError):self.verify([SimpleNamespace(**(self.fields|{key:value}))])
        with self.assertRaises(AuditExportWorkerError):self.verify([SimpleNamespace(**(self.fields|{'occurred_at':self.requested-timedelta(seconds=1)}))])

    def test_unique_and_recovery_action_reason(self):
        row=SimpleNamespace(**(self.fields|{'action':'AUDIT_EXPORT_CANCEL_RECOVERED','reason_code':'LEASE_EXPIRED'}))
        self.assertEqual(self.verify([row],expired=True),row.audit_event_id)
        for rows in ([],[row,row]):
            with self.assertRaises(AuditExportWorkerError):self.verify(rows,expired=True)
        self.session.scalar.return_value.occurred_at=self.now+timedelta(seconds=1)
        with self.assertRaises(AuditExportWorkerError):self.verify([row],expired=True)
