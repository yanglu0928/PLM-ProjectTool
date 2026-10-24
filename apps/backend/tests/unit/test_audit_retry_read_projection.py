import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock
from plm_assistant.modules.audit.application.job_read_projection import AuditJobReadProjection
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent, AcceptedAuditExport
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.user_retry_source import AuditUserRetrySource
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobFailure
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts, JobReadError
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class AuditRetryReadProjectionTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        spec=AuditExportSpec('PROJECT',uuid4(),'PROJECT_GOVERNANCE',now-timedelta(hours=1),now)
        intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),now,spec,spec.fingerprint())
        self.accepted=AcceptedAuditExport(intent,uuid4(),uuid4(),uuid4(),now)
        self.facts=JobReadFacts(self.accepted.job_id,'audit','AUDIT_EXPORT','PROJECT',spec.project_id,
            intent.actor_id,'FAILED',3,now,now,3)
        self.actor=uuid4(); self.tx=object()
        self.repo=Mock(); self.repo.get_created_for_job.return_value=intent
        self.repo.get_accepted.return_value=self.accepted
        self.queue=Mock(); self.queue.find_export.return_value=AuditExportJobRef(self.accepted.job_id,self.accepted.event_id)
        self.results=Mock(); self.sources=Mock(); self.projects=Mock()
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(
            self.actor,spec.project_id,'AUDIT_PROJECT_EXPORT','PROJECT_MANAGER')
        self.source=AuditUserRetrySource(self.accepted,AuditUserRetryJobFailure(self.accepted.job_id,3,3,now,now),uuid4())
        self.sources.read.return_value=self.source
        self.owner=AuditJobReadProjection(repository=self.repo,queue=self.queue,results=self.results,
            retry_sources=self.sources,retry_projects=self.projects)

    def read(self,role='PROJECT_MANAGER',facts=None,owner=None):
        return (owner or self.owner).project(self.tx,facts=facts or self.facts,actor_id=self.actor,project_role=role)

    def test_current_export_permission_and_exact_failure_required(self):
        self.assertTrue(self.read().retryable)
        self.projects.require_in_transaction.assert_called_once_with(self.tx,user_id=self.actor,
            project_id=self.facts.project_id,operation='AUDIT_PROJECT_EXPORT')
        self.sources.read.assert_called_once_with(self.tx,accepted=self.accepted,expected_version=3)

    def test_readonly_and_non_manager_never_consult_retry_source(self):
        readonly=AuditJobReadProjection(repository=self.repo,queue=self.queue,results=self.results)
        self.assertFalse(self.read(owner=readonly).retryable)
        for role in ('IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER',None):
            self.assertFalse(self.read(role=role).retryable)
        self.sources.read.assert_not_called(); self.projects.require_in_transaction.assert_not_called()

    def test_non_failed_state_never_reads_failure(self):
        for state in ('PENDING','RUNNING','RETRY_WAIT','CANCEL_REQUESTED','CANCELLED'):
            facts=replace(self.facts,state=state,completed_at=self.facts.completed_at if state=='CANCELLED' else None)
            self.assertFalse(self.read(facts=facts).retryable)
        self.sources.read.assert_not_called()

    def test_known_nonretryable_is_false_but_corrupt_or_unavailable_source_is_error(self):
        self.sources.read.side_effect=JobLeaseError('JOB_NOT_RETRYABLE')
        self.assertFalse(self.read().retryable)
        for error in (JobLeaseError('VERSION_CONFLICT'),JobLeaseError('JOB_STORE_UNAVAILABLE'),RuntimeError('private SQL')):
            self.sources.read.side_effect=error
            with self.assertRaises(JobReadError) as caught:self.read()
            self.assertEqual(caught.exception.code,'JOB_UNAVAILABLE')
            self.assertNotIn('private',str(caught.exception))

    def test_wrong_current_permission_never_reads_source(self):
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(
            uuid4(),self.facts.project_id,'AUDIT_PROJECT_EXPORT','PROJECT_MANAGER')
        with self.assertRaises(JobReadError):self.read()
        self.sources.read.assert_not_called()

    def test_source_version_and_original_acceptance_are_exact(self):
        for source in (object(),replace(self.source,failure=replace(self.source.failure,lock_version=4))):
            self.sources.read.return_value=source
            with self.assertRaises(JobReadError):self.read()
        self.repo.get_accepted.return_value=replace(self.accepted,event_id=uuid4())
        self.sources.reset_mock()
        with self.assertRaises(JobReadError):self.read()
        self.sources.read.assert_not_called()

    def test_injected_source_requires_current_project_policy(self):
        with self.assertRaises(ValueError):AuditJobReadProjection(repository=self.repo,queue=self.queue,
            results=self.results,retry_sources=self.sources)
