from __future__ import annotations
import unittest,uuid
from plm_assistant.modules.jobs.application.output_enqueue import OutputJobEnqueueError,OutputJobQueue
class Repo:
    def __init__(self):self.calls=[]
    def enqueue_output(self,tx,**kwargs):self.calls.append((tx,kwargs));return uuid.uuid4()
class OutputJobTests(unittest.TestCase):
    def test_forwards_to_caller_transaction(self):
        repo=Repo();queue=OutputJobQueue(repo);tx=object()
        values=dict(project_id=uuid.uuid4(),output_request_id=uuid.uuid4(),
            context_snapshot_id=uuid.uuid4(),actor_id=uuid.uuid4(),trace_id=uuid.uuid4())
        self.assertTrue(queue.enqueue_output(tx,**values).int)
        self.assertEqual(repo.calls,[(tx,values)])
    def test_rejects_invalid_ref(self):
        repo=Repo()
        with self.assertRaisesRegex(OutputJobEnqueueError,"VALIDATION_FAILED"):
            OutputJobQueue(repo).enqueue_output(object(),project_id=uuid.uuid4(),
                output_request_id=uuid.uuid4(),context_snapshot_id=None,
                actor_id=uuid.uuid4(),trace_id=uuid.uuid4())
        self.assertEqual(repo.calls,[])
if __name__=="__main__":unittest.main()
