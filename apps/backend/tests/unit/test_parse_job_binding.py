from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue,ParseJobRequest,ParseJobRef,ParseJobBinding,ParseEnqueueError

class ParseBindingTests(TestCase):
    def setUp(self):
        self.repo=Mock();self.queue=ParseJobQueue(self.repo)
        self.request=ParseJobRequest(uuid4(),uuid4(),uuid4(),1,'GLOBAL',None,uuid4(),uuid4())
        self.refs=ParseJobRef(uuid4(),uuid4());self.binding=ParseJobBinding(self.request,self.refs)
    def test_typed_reads_do_not_enqueue(self):
        self.repo.peek_parse_for_job.return_value=self.binding;self.repo.find_parse.return_value=self.refs
        self.assertEqual(self.queue.peek_parse_for_job(object(),job_id=self.refs.job_id),self.binding)
        self.assertEqual(self.queue.find_parse(object(),request=self.request),self.refs)
        self.repo.enqueue_parse.assert_not_called()
    def test_absent_reads_never_create(self):
        self.repo.peek_parse_for_job.return_value=None;self.repo.find_parse.return_value=None
        self.assertIsNone(self.queue.peek_parse_for_job(object(),job_id=self.refs.job_id))
        self.assertIsNone(self.queue.find_parse(object(),request=self.request))
        self.repo.enqueue_parse.assert_not_called()
    def test_untrusted_wrong_binding_or_store_details_reject(self):
        self.repo.peek_parse_for_job.return_value=ParseJobBinding(self.request,ParseJobRef(uuid4(),uuid4()))
        with self.assertRaises(ParseEnqueueError):self.queue.peek_parse_for_job(object(),job_id=self.refs.job_id)
        self.repo.find_parse.side_effect=RuntimeError('private DB path')
        with self.assertRaises(ParseEnqueueError) as caught:self.queue.find_parse(object(),request=self.request)
        self.assertEqual(str(caught.exception),'JOB_STORE_UNAVAILABLE')
        self.repo.enqueue_parse.assert_not_called()
    def test_strict_read_input_before_repository(self):
        for values in (dict(version_no=True),dict(version_no=0),dict(version_no=2**31),dict(scope='PROJECT'),dict(trace_id=None)):
            with self.assertRaises(ParseEnqueueError):self.queue.find_parse(object(),request=replace(self.request,**values))
        self.repo.find_parse.assert_not_called()
