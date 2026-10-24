from dataclasses import replace
from datetime import datetime,timezone
from threading import Event
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_termination as fixture
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelReceipt
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancelFacts,AuditExportCancellationResult


class WorkerCancelTests(TestCase):
    def setUp(self):
        f=fixture.WorkerTerminationTests();f.setUp();self.f=f
        self.cancel,self.sources=Mock(),Mock()
        self.facts=AuditExportCancelFacts(f.f.cmd.job_id,'CANCEL_REQUESTED',f.f.intent.actor_id,datetime.now(timezone.utc),'Synthetic private reason')
        self.cancel.read_facts.return_value=self.facts
        self.sources.first_request.return_value=AuditExportCancelReceipt(f.f.cmd.job_id,'CANCEL_REQUESTED',True,uuid4())
        self.cancel.acknowledge_cancel.return_value=AuditExportCancellationResult(f.f.cmd.job_id,'CANCELLED',True)
        self.owner=AuditExportWorkerCancel(unit_of_work=f.f.uow,repository=f.f.repo,cancellations=self.cancel,
            sources=self.sources,audit=f.audit,system_actor=f.actor,supervisor=f.supervisor)

    def test_original_scope_source_system_event_and_ack_last(self):
        self.assertEqual(self.owner.acknowledge(self.f.f.cmd).state,'CANCELLED')
        event=self.f.audit.append.call_args.args[1]
        self.assertEqual((event.actor_type,event.original_actor_id,event.trace_id,event.action),
            ('SYSTEM',self.f.f.intent.actor_id,self.f.f.intent.trace_id,'AUDIT_EXPORT_CANCELLED'))
        self.assertNotIn(self.facts.reason,repr(event));self.f.f.tx.commit.assert_called_once()
        self.f.f.auth.assert_current.assert_not_called()

    def test_missing_or_immediate_first_source_never_acks(self):
        for first in (None,replace(self.sources.first_request.return_value,state='CANCELLED'),replace(self.sources.first_request.return_value,job_id=uuid4())):
            self.sources.first_request.return_value=first
            with self.assertRaises(AuditExportWorkerError):self.owner.acknowledge(self.f.f.cmd)
        self.cancel.acknowledge_cancel.assert_not_called();self.f.f.tx.commit.assert_not_called()

    def test_post_audit_identity_loss_never_acks(self):
        self.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError) as cm:self.owner.acknowledge(self.f.f.cmd)
        self.assertEqual(cm.exception.code,'SYSTEM_ACTOR_UNAVAILABLE');self.cancel.acknowledge_cancel.assert_not_called()

    def test_invalid_command_and_live_thread_refuse(self):
        with self.assertRaises(AuditExportWorkerError):self.owner.acknowledge(True)
        entered,release=Event(),Event()
        def busy(*args,**kwargs):entered.set();release.wait(3);return self.f.f.claim
        self.f.heartbeats.heartbeat.side_effect=busy
        handle=self.f.supervisor.start(self.f.f.cmd,lease_seconds=3,interval_seconds=.1)
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(AuditExportWorkerError):self.owner.acknowledge(self.f.f.cmd)
            self.f.f.uow.assert_not_called()
        finally:release.set();handle.stop()
