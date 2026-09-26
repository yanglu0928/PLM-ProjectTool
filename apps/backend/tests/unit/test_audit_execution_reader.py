from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_cancel as fixture
from plm_assistant.modules.audit.application.read_execution_facts import AuditExportExecutionReader
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionFacts
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class ExecutionReaderTests(TestCase):
    def setUp(self):
        f=fixture.WorkerCancelTests();f.setUp();self.f=f
        self.facts=AuditExportExecutionFacts(f.f.f.claim,f.f.f.cmd.fencing_token,'RUNNING','ACTIVE',True,None)
        self.port=Mock();self.port.read.return_value=self.facts
        self.owner=AuditExportExecutionReader(execution_facts=self.port,unit_of_work=f.f.f.uow,
            repository=f.f.f.repo,cancellations=f.cancel,sources=f.sources,audit=f.f.audit,system_actor=f.f.actor,supervisor=f.f.supervisor)

    def test_current_hint_without_commit_auth_or_mutation(self):
        self.assertEqual(self.owner.read(self.f.f.f.cmd),self.facts)
        self.assertTrue(self.facts.is_current)
        self.f.f.f.tx.commit.assert_not_called();self.f.f.audit.append.assert_not_called()
        self.f.f.f.auth.assert_current.assert_not_called();self.f.cancel.acknowledge_cancel.assert_not_called()

    def test_historical_hint_is_not_current(self):
        self.port.read.return_value=replace(self.facts,current_fencing_token=2,lease_state='RELEASED',lease_alive=False)
        self.assertFalse(self.owner.read(self.f.f.f.cmd).is_current)
        self.f.f.f.tx.commit.assert_not_called()

    def test_invalid_counter_type_and_free_error_body_refuse(self):
        for change in (dict(current_fencing_token=True),dict(claim=replace(self.facts.claim,attempt_no=True)),dict(error_code='private/path secret')):
            with self.assertRaises(JobLeaseError):replace(self.facts,**change)

    def test_inconsistent_active_or_historical_hint_refuse(self):
        for change in (dict(state='SUCCEEDED'),dict(current_fencing_token=2),dict(error_code='AUDIT_UNAVAILABLE'),dict(lease_state='RELEASED')):
            with self.assertRaises(JobLeaseError):replace(self.facts,**change)

    def test_foreign_claim_invalid_command_and_identity_refuse(self):
        with self.assertRaises(AuditExportWorkerError):self.owner.read(True)
        self.f.f.f.uow.assert_not_called()
        self.port.read.return_value=replace(self.facts,claim=replace(self.facts.claim,job_id=uuid4()))
        with self.assertRaises(AuditExportWorkerError):self.owner.read(self.f.f.f.cmd)
        self.port.read.return_value=self.facts;self.f.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.owner.read(self.f.f.f.cmd)
        self.f.f.f.tx.commit.assert_not_called()
