from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import UUID, uuid4
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal


class JobLeaseRenewalTests(TestCase):
    def setUp(self):
        self.repo, self.tx = Mock(), Mock()
        self.args = dict(job_id=uuid4(), fencing_token=2, worker_ref='worker', lease_seconds=60)
        self.claim = ClaimedJob(self.args['job_id'],'AUDIT_EXPORT','DEPLOYMENT',None,{},str(uuid4()),2,1)
        self.repo.check_current.return_value=self.claim; self.repo.heartbeat.return_value=None
        self.service=JobLeaseRenewal(repository=self.repo)

    def test_check_renew_check_caller_uow_no_commit(self):
        self.assertEqual(self.service.renew_current(self.tx,**self.args),self.claim)
        self.assertEqual([c[0] for c in self.repo.mock_calls],['check_current','heartbeat','check_current'])
        self.repo.heartbeat.assert_called_once_with(self.tx,**self.args)
        self.tx.commit.assert_not_called()

    def test_invalid_before_repository(self):
        for field,values in (('lease_seconds',(True,0,-1,3601,'60',None)),
                             ('job_id',(UUID(int=0),True)),('fencing_token',(True,0)),('worker_ref',('',True))):
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaises(JobLeaseError):
                    self.service.renew_current(self.tx,**(self.args|{field:value}))
        self.repo.check_current.assert_not_called();self.repo.heartbeat.assert_not_called()

    def test_stale_precheck_never_renews(self):
        self.repo.check_current.side_effect=JobLeaseError('STALE_LEASE')
        with self.assertRaises(JobLeaseError):self.service.renew_current(self.tx,**self.args)
        self.repo.heartbeat.assert_not_called()

    def test_postcheck_changed_claim_or_expiry_no_commit(self):
        for value in (replace(self.claim,payload_refs={'changed':True}),replace(self.claim,attempt_no=2),JobLeaseError('STALE_LEASE')):
            self.repo.check_current.side_effect=[self.claim,value]
            with self.assertRaises(JobLeaseError):self.service.renew_current(self.tx,**self.args)
        self.tx.commit.assert_not_called()

    def test_unexpected_renewal_result_rejected(self):
        self.repo.heartbeat.return_value=True
        with self.assertRaises(JobLeaseError):self.service.renew_current(self.tx,**self.args)
        with self.assertRaises(ValueError):JobLeaseRenewal(repository=None)
