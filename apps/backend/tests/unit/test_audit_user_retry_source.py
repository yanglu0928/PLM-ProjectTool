import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobFailure, AuditUserRetryJobSources
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.audit.application.user_retry_source import AuditUserRetrySourceReader, AuditUserRetrySource
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent, AcceptedAuditExport
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError

class UserRetrySourcesTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        spec=AuditExportSpec('PROJECT',uuid4(),'PROJECT_GOVERNANCE',self.now-timedelta(hours=1),self.now)
        intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),self.now,spec,spec.fingerprint())
        self.accepted=AcceptedAuditExport(intent,uuid4(),uuid4(),uuid4(),self.now)
        self.refs=AuditExportJobRef(self.accepted.job_id,self.accepted.event_id)
        self.request=AuditExportJobRequest(intent.export_id,intent.actor_id,spec.scope,spec.project_id,intent.trace_id)
        self.failure=AuditUserRetryJobFailure(self.refs.job_id,3,3,self.now,self.now)

    def test_typed_technical_facts_reject_invalid_or_earlier_times(self):
        for changes in ({'job_id':UUID(int=0)},{'lock_version':True},{'lock_version':-1},
            {'lock_version':9223372036854775808},{'attempt_no':2},{'attempt_no':True},
            {'started_at':datetime.now()},{'completed_at':self.now-timedelta(seconds=1)}):
            with self.subTest(changes=changes), self.assertRaises(JobLeaseError): replace(self.failure,**changes)
        self.assertEqual(set(self.failure.__dataclass_fields__),{'job_id','lock_version','attempt_no','started_at','completed_at'})

    def test_owned_job_pair_proof_and_exact_result(self):
        queue=Mock();queue.find_export.return_value=self.refs
        repo=Mock();repo.read_failed.return_value=self.failure
        source=AuditUserRetryJobSources(queue=queue,repository=repo)
        tx=object()
        self.assertEqual(source.read_failed(tx,request=self.request,refs=self.refs,expected_version=3),self.failure)
        queue.find_export.assert_called_once_with(tx,request=self.request)
        repo.read_failed.assert_called_once()
        queue.find_export.return_value=AuditExportJobRef(uuid4(),uuid4())
        repo.reset_mock()
        with self.assertRaises(JobLeaseError): source.read_failed(tx,request=self.request,refs=self.refs,expected_version=3)
        repo.read_failed.assert_not_called()

    def test_store_faults_safe_and_version_errors_preserved(self):
        queue=Mock();queue.find_export.return_value=self.refs;repo=Mock()
        source=AuditUserRetryJobSources(queue=queue,repository=repo)
        for error in (RuntimeError('private query text'), JobLeaseError('VERSION_CONFLICT'), JobLeaseError('JOB_NOT_RETRYABLE')):
            repo.read_failed.side_effect=error
            with self.assertRaises(JobLeaseError) as caught: source.read_failed(object(),request=self.request,refs=self.refs,expected_version=3)
            self.assertNotIn('private',str(caught.exception))
            self.assertEqual(caught.exception.code, error.code if isinstance(error,JobLeaseError) else 'JOB_STORE_UNAVAILABLE')
        repo.read_failed.side_effect=None
        for value in (object(),replace(self.failure,job_id=uuid4()),replace(self.failure,lock_version=4)):
            repo.read_failed.return_value=value
            with self.assertRaises(JobLeaseError): source.read_failed(object(),request=self.request,refs=self.refs,expected_version=3)

    def test_bad_version_never_reads_technical_store(self):
        queue=Mock();repo=Mock(); source=AuditUserRetryJobSources(queue=queue,repository=repo)
        for value in (True,-1,9223372036854775808,'3'):
            with self.assertRaises(JobLeaseError): source.read_failed(object(),request=self.request,refs=self.refs,expected_version=value)
        queue.find_export.assert_not_called();repo.read_failed.assert_not_called()

    def test_audit_source_binds_original_before_owned_jobs(self):
        repo=Mock();repo.get_created.return_value=self.accepted.intent;repo.get_accepted.return_value=self.accepted
        jobs=Mock();jobs.read_failed.return_value=self.failure
        audits=Mock();audits.read_failure.return_value=uuid4()
        reader=AuditUserRetrySourceReader(repository=repo,jobs=jobs,failures=audits)
        result=reader.read(object(),accepted=self.accepted,expected_version=3)
        self.assertEqual(result.accepted,self.accepted);self.assertEqual(result.failure,self.failure)
        repo.get_accepted.return_value=None;jobs.reset_mock();audits.reset_mock()
        with self.assertRaises(AuditExportWorkerError): reader.read(object(),accepted=self.accepted,expected_version=3)
        jobs.read_failed.assert_not_called();audits.read_failure.assert_not_called()

    def test_audit_result_requires_exact_source_and_failure_time(self):
        with self.assertRaises(AuditExportWorkerError): AuditUserRetrySource(self.accepted,replace(self.failure,job_id=uuid4()),uuid4())
        with self.assertRaises(AuditExportWorkerError): AuditUserRetrySource(self.accepted,self.failure,UUID(int=0))
        early=replace(self.failure,started_at=self.now-timedelta(seconds=1))
        with self.assertRaises(AuditExportWorkerError): AuditUserRetrySource(self.accepted,early,uuid4())

    def test_bad_job_port_never_reads_audit_as_authority(self):
        repo=Mock();repo.get_created.return_value=self.accepted.intent;repo.get_accepted.return_value=self.accepted
        jobs=Mock();audits=Mock()
        reader=AuditUserRetrySourceReader(repository=repo,jobs=jobs,failures=audits)
        for value in (object(),replace(self.failure,job_id=uuid4()),replace(self.failure,lock_version=4)):
            jobs.read_failed.return_value=value
            with self.assertRaises(AuditExportWorkerError): reader.read(object(),accepted=self.accepted,expected_version=3)
        audits.read_failure.assert_not_called()
