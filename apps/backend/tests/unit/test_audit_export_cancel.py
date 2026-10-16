import unittest
from dataclasses import replace
from unittest.mock import Mock
from uuid import UUID,uuid4
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_cancel import (
    AuditExportCancellation,AuditExportCancellationTarget,AuditExportCancellationResult,
    AuditExportCancellationError,
)


class ExportCancelTests(unittest.TestCase):
    def setUp(self):
        self.repo,self.tx=Mock(),Mock()
        self.service=AuditExportCancellation(repository=self.repo)
        self.target=AuditExportCancellationTarget(AuditExportJobRequest(uuid4(),uuid4(),"DEPLOYMENT",None,uuid4()),AuditExportJobRef(uuid4(),uuid4()))
        self.args=dict(target=self.target,requested_by=uuid4(),reason="合成取消原因")
        self.result=AuditExportCancellationResult(self.target.refs.job_id,"CANCEL_REQUESTED",True)
        self.repo.request_cancel.return_value=self.result

    def test_request_uses_caller_transaction_and_no_commit(self):
        self.assertEqual(self.service.request_cancel(self.tx,**self.args),self.result)
        self.repo.request_cancel.assert_called_once_with(self.tx,**self.args)
        self.tx.commit.assert_not_called()
        self.assertNotIn("reason",vars(type(self.result)))

    def test_reason_user_target_validation_before_repository(self):
        for reason in (None,True,""," "," leading","trailing ","x"*1025,"a\nb","a\x00b","a\u200bb"):
            with self.assertRaises(AuditExportCancellationError):self.service.request_cancel(self.tx,**(self.args|dict(reason=reason)))
        for actor in (None,str(uuid4()),UUID(int=0)):
            with self.assertRaises(AuditExportCancellationError):self.service.request_cancel(self.tx,**(self.args|dict(requested_by=actor)))
        with self.assertRaises(AuditExportCancellationError):self.service.request_cancel(self.tx,**(self.args|dict(target=True)))
        self.repo.request_cancel.assert_not_called()

    def test_nested_mutation_is_revalidated(self):
        object.__setattr__(self.target.request,"scope","GLOBAL")
        with self.assertRaises(AuditExportCancellationError):self.service.recover_expired_cancel(self.tx,target=self.target)
        self.repo.recover_expired_cancel.assert_not_called()

    def test_result_identity_and_terminal_not_changed(self):
        for result in (None,True,replace(self.result,job_id=uuid4())):
            self.repo.request_cancel.return_value=result
            with self.assertRaises(AuditExportCancellationError):self.service.request_cancel(self.tx,**self.args)
        for state in ("SUCCEEDED","FAILED"):
            with self.assertRaises(AuditExportCancellationError):replace(self.result,state=state)
            result=replace(self.result,state=state,changed=False)
            self.repo.request_cancel.return_value=result
            self.assertEqual(self.service.request_cancel(self.tx,**self.args),result)

    def test_ack_validation_and_required_cancelled_result(self):
        for token in (True,0,-1,2**63):
            with self.assertRaises(AuditExportCancellationError):self.service.acknowledge_cancel(self.tx,target=self.target,fencing_token=token,worker_ref="worker")
        self.repo.acknowledge_cancel.assert_not_called()
        self.repo.acknowledge_cancel.return_value=self.result
        with self.assertRaises(AuditExportCancellationError):self.service.acknowledge_cancel(self.tx,target=self.target,fencing_token=1,worker_ref="worker")
        self.repo.acknowledge_cancel.return_value=replace(self.result,state="CANCELLED")
        self.service.acknowledge_cancel(self.tx,target=self.target,fencing_token=1,worker_ref="worker")

    def test_recovery_result_safe_errors_and_no_fallback(self):
        self.repo.recover_expired_cancel.return_value=self.result
        with self.assertRaises(AuditExportCancellationError):self.service.recover_expired_cancel(self.tx,target=self.target)
        self.repo.request_cancel.side_effect=RuntimeError("unsafe SQL storage detail")
        with self.assertRaises(AuditExportCancellationError) as caught:self.service.request_cancel(self.tx,**self.args)
        self.assertEqual(str(caught.exception),"JOB_STORE_UNAVAILABLE")
        with self.assertRaises(ValueError):AuditExportCancellation(repository=None)
