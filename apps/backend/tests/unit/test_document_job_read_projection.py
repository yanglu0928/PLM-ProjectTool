import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection
from plm_assistant.modules.document.application.parse_job_source import CommittedParseDocumentSource, DocumentParseSourceError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding, ParseJobRef, ParseJobRequest
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts, JobReadError


class DocumentJobProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tx = Mock()
        self.actor, self.pid, self.job = uuid4(), uuid4(), uuid4()
        self.now = datetime.now(timezone.utc)
        self.request = ParseJobRequest(uuid4(), uuid4(), uuid4(), 1, 'PROJECT', self.pid, self.actor, uuid4())
        self.refs = ParseJobRef(self.job, uuid4())
        self.binding = ParseJobBinding(self.request, self.refs)
        self.source = CommittedParseDocumentSource(self.request, uuid4(), self.now)
        self.facts = JobReadFacts(self.job, 'document', 'DOCUMENT_PARSE', 'PROJECT', self.pid, self.actor, 'PENDING', 0, self.now, None)
        self.queue, self.sources = Mock(), Mock()
        self.queue.peek_parse_for_job.return_value = self.binding
        self.queue.find_parse.return_value = self.refs
        self.sources.read.return_value = self.source
        self.owner = DocumentParseJobReadProjection(queue=self.queue, sources=self.sources)

    def read(self, facts=None):
        return self.owner.project(self.tx, facts=facts or self.facts, actor_id=uuid4(), project_role='PROJECT_MANAGER')

    def assert_error(self, code, facts=None):
        with self.assertRaises(JobReadError) as cm:
            self.read(facts)
        self.assertEqual(str(cm.exception), code)
        self.tx.commit.assert_not_called()

    def test_source_before_pair_same_transaction_no_write_or_result(self):
        order = Mock()
        order.attach_mock(self.queue, 'queue'); order.attach_mock(self.sources, 'source')
        value = self.read()
        self.assertEqual([call[0] for call in order.mock_calls], ['queue.peek_parse_for_job', 'source.read', 'queue.find_parse'])
        self.sources.read.assert_called_once_with(self.tx, request=self.request)
        self.queue.find_parse.assert_called_once_with(self.tx, request=self.request)
        self.assertEqual((value.job_id, value.retryable, value.result_id), (self.job, False, None))
        self.tx.commit.assert_not_called()

    def test_wrong_original_coordinates_and_owner_rejected(self):
        for changes in ({'actor_id': uuid4()}, {'project_id': uuid4()}, {'scope': 'GLOBAL', 'project_id': None}, {'job_id': uuid4()}):
            self.assert_error('JOB_UNAVAILABLE', replace(self.facts, **changes))
        self.sources.read.assert_not_called()
        self.assert_error('RESOURCE_NOT_FOUND', replace(self.facts, owner_module='audit'))

    def test_wrong_source_or_pair_fails_closed(self):
        self.sources.read.return_value = replace(self.source, request=replace(self.request, trace_id=uuid4()))
        self.assert_error('JOB_UNAVAILABLE'); self.queue.find_parse.assert_not_called()
        self.sources.read.return_value = self.source
        for refs in (None, ParseJobRef(self.job, uuid4()), ParseJobRef(uuid4(), self.refs.event_id)):
            self.queue.find_parse.return_value = refs
            self.assert_error('JOB_UNAVAILABLE')

    def test_hidden_missing_and_static_exception(self):
        self.queue.peek_parse_for_job.return_value = None
        self.assert_error('RESOURCE_NOT_FOUND')
        self.queue.peek_parse_for_job.return_value = self.binding
        self.sources.read.side_effect = DocumentParseSourceError('RESOURCE_NOT_FOUND')
        self.assert_error('RESOURCE_NOT_FOUND')
        self.sources.read.side_effect = RuntimeError('private path and SQL')
        self.assert_error('JOB_UNAVAILABLE')

    def test_success_requires_real_result_proof_not_version_guess(self):
        self.assert_error('JOB_UNAVAILABLE', replace(self.facts, state='SUCCEEDED', completed_at=self.now))
        self.queue.find_parse.assert_called_once()

    def test_global_exact_coordinates_and_other_non_success_states(self):
        request = replace(self.request, scope='GLOBAL', project_id=None)
        self.queue.peek_parse_for_job.return_value = ParseJobBinding(request, self.refs)
        self.sources.read.return_value = replace(self.source, request=request)
        self.assertIsNone(self.read(replace(self.facts, scope='GLOBAL', project_id=None)).result_id)
        self.queue.peek_parse_for_job.return_value = self.binding
        self.sources.read.return_value = self.source
        for state in ('RUNNING', 'RETRY_WAIT', 'CANCEL_REQUESTED', 'FAILED', 'CANCELLED'):
            facts = replace(self.facts, state=state, completed_at=self.now if state in ('FAILED', 'CANCELLED') else None)
            self.assertIsNone(self.read(facts).result_id)
