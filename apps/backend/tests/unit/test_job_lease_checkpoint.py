import unittest
from dataclasses import replace
from unittest.mock import Mock
from uuid import UUID, uuid4
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import JobLeaseCheckpoint


class LeaseCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.repo,self.tx=Mock(),Mock()
        self.service=JobLeaseCheckpoint(repository=self.repo)
        self.args=dict(job_id=uuid4(),fencing_token=3,worker_ref="worker-1")
        self.claim=ClaimedJob(self.args['job_id'],"AUDIT_EXPORT","DEPLOYMENT",None,{},str(uuid4()),3,2)
        self.repo.check_current.return_value=self.claim

    def test_caller_transaction_only(self):
        self.assertIs(self.service.check_current(self.tx,**self.args),self.claim)
        self.repo.check_current.assert_called_once_with(self.tx,**self.args)
        self.tx.commit.assert_not_called()

    def test_validation_before_repository(self):
        invalid=dict(job_id=[None,str(uuid4()),UUID(int=0)],fencing_token=[True,0,-1,2**63,"3"],worker_ref=[True,None,""," worker","worker ","w"*129])
        for key,values in invalid.items():
            for value in values:
                with self.subTest(key=key,value=value),self.assertRaises(JobLeaseError):
                    self.service.check_current(self.tx,**(self.args|{key:value}))
        self.repo.check_current.assert_not_called()

    def test_result_identity_and_generation(self):
        for claim in (True,None,replace(self.claim,job_id=uuid4()),replace(self.claim,fencing_token=True),replace(self.claim,fencing_token=4),replace(self.claim,attempt_no=True),replace(self.claim,attempt_no=0)):
            self.repo.check_current.return_value=claim
            with self.assertRaises(JobLeaseError) as caught:self.service.check_current(self.tx,**self.args)
            self.assertEqual(caught.exception.code,"JOB_STORE_UNAVAILABLE")

    def test_stale_propagates_and_no_fallback(self):
        self.repo.check_current.side_effect=JobLeaseError("STALE_LEASE")
        with self.assertRaises(JobLeaseError) as caught:self.service.check_current(self.tx,**self.args)
        self.assertEqual(caught.exception.code,"STALE_LEASE")
        with self.assertRaises(ValueError):JobLeaseCheckpoint(repository=None)
