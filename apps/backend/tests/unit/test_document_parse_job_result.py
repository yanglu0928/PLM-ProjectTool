import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.document.application.parse_job_result import DocumentParseJobResults, ParseJobResultSource
from plm_assistant.modules.document.application.parse_job_source import CommittedParseDocumentSource
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobRequest, ParseJobRef, ParseJobBinding
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts, JobReadError


class ParseResultTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.job, self.pid, self.actor = uuid4(), uuid4(), uuid4()
        self.request = ParseJobRequest(uuid4(), uuid4(), uuid4(), 1, 'PROJECT', self.pid, self.actor, uuid4())
        self.source = CommittedParseDocumentSource(self.request, uuid4(), self.now)
        self.facts = JobReadFacts(self.job, 'document', 'DOCUMENT_PARSE', 'PROJECT', self.pid, self.actor, 'SUCCEEDED', 1,
            self.now, self.now + timedelta(seconds=5))
        self.result = ParseJobResultSource(uuid4(), self.job, self.request.document_version_id, 'PROJECT', self.pid,
            uuid4(), b'h' * 32, self.now, self.now + timedelta(seconds=1), self.now + timedelta(seconds=4), self.now + timedelta(seconds=3))
        self.repo = Mock(); self.repo.get.return_value = self.result
        self.service = DocumentParseJobResults(repository=self.repo)
        self.tx = Mock()

    def read(self): return self.service.read(self.tx, facts=self.facts, source=self.source)

    def test_exact_same_uow_source_and_safe_logical_projection(self):
        self.assertEqual(self.read(), self.result)
        queue, sources = Mock(), Mock()
        refs = ParseJobRef(self.job, uuid4())
        queue.peek_parse_for_job.return_value = ParseJobBinding(self.request, refs)
        queue.find_parse.return_value = refs; sources.read.return_value = self.source
        projection = DocumentParseJobReadProjection(queue=queue, sources=sources, results=self.service).project(
            self.tx, facts=self.facts, actor_id=self.actor, project_role='PROJECT_MANAGER')
        self.assertEqual((projection.result_type, projection.result_id), ('DOCUMENT_PARSE', self.result.parse_record_id))
        self.assertNotEqual(projection.result_id, self.result.result_ref_id)
        self.assertFalse(hasattr(self.result, 'storage_locator'))
        self.tx.commit.assert_not_called()

    def test_source_coordinates_and_time_mismatch_fail(self):
        for changes in ({'job_id': uuid4()}, {'document_version_id': uuid4()}, {'project_id': uuid4()},
            {'scope': 'GLOBAL', 'project_id': None}, {'created_at': self.now - timedelta(seconds=1)},
            {'completed_at': self.now + timedelta(seconds=6)}):
            self.repo.get.return_value = replace(self.result, **changes)
            with self.assertRaises(JobReadError): self.read()

    def test_missing_untyped_exception_sanitized(self):
        for result in (None, object()):
            self.repo.get.return_value = result
            with self.assertRaises(JobReadError) as cm: self.read()
            self.assertEqual(str(cm.exception), 'JOB_UNAVAILABLE')
        self.repo.get.side_effect = RuntimeError('private SQL and path')
        with self.assertRaises(JobReadError) as cm: self.read()
        self.assertEqual(str(cm.exception), 'JOB_UNAVAILABLE')

    def test_strict_dto_and_non_success_no_repository(self):
        for changes in ({'sha256': b'x'}, {'parse_record_id': uuid4().__str__()}, {'project_id': None},
            {'started_at': datetime.now()}, {'result_created_at': self.now - timedelta(seconds=1)}):
            with self.assertRaises(JobReadError): replace(self.result, **changes)
        self.facts = replace(self.facts, state='RUNNING', completed_at=None)
        with self.assertRaises(JobReadError): self.read()
        self.repo.get.assert_not_called()
