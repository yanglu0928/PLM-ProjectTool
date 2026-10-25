from dataclasses import replace,FrozenInstanceError
from uuid import uuid4,UUID
from unittest.mock import Mock
import unittest
from plm_assistant.modules.jobs.application.audit_export_enqueue import (
    AuditExportJobRequest,AuditExportJobRef,AuditExportJobQueue,AuditExportEnqueueError,
)
from plm_assistant.modules.jobs.infrastructure.audit_export_enqueue_repository import _lock_key


class AuditExportEnqueueTests(unittest.TestCase):
    def setUp(self):
        self.request=AuditExportJobRequest(uuid4(),uuid4(),"DEPLOYMENT",None,uuid4())
        self.repo=Mock();self.ref=AuditExportJobRef(uuid4(),uuid4())
        self.repo.enqueue_export.return_value=self.ref;self.repo.find_export.return_value=self.ref
        self.queue=AuditExportJobQueue(self.repo);self.tx=Mock()

    def test_minimal_request_and_ref_and_same_caller_tx(self):
        self.assertEqual(self.queue.enqueue_export(self.tx,request=self.request),self.ref)
        self.repo.enqueue_export.assert_called_once_with(self.tx,request=self.request)
        self.assertEqual(self.queue.find_export(self.tx,request=self.request),self.ref)
        self.tx.commit.assert_not_called();self.tx.rollback.assert_not_called()
        self.assertEqual(set(self.request.__dataclass_fields__),{"export_id","actor_id","scope","project_id","trace_id","policy_version"})
        self.assertEqual(set(self.ref.__dataclass_fields__),{"job_id","event_id"})
        with self.assertRaises(FrozenInstanceError):self.request.scope="GLOBAL"

    def test_scope_uuid_and_policy_validation(self):
        for changed in (dict(scope="GLOBAL"),dict(scope="PROJECT"),dict(project_id=uuid4()),dict(export_id=UUID(int=0)),dict(actor_id=True),dict(trace_id="text"),dict(policy_version="OTHER")):
            with self.subTest(changed=changed),self.assertRaises(AuditExportEnqueueError):replace(self.request,**changed)
        good=replace(self.request,scope="PROJECT",project_id=uuid4())
        self.assertEqual(good.scope,"PROJECT")
        self.assertEqual(good.policy_version,"AUDIT-EXPORT-POLICY-V1")

    def test_corrupted_request_before_repository(self):
        object.__setattr__(self.request,"scope","GLOBAL")
        for method in (self.queue.enqueue_export,self.queue.find_export):
            with self.assertRaises(AuditExportEnqueueError):method(self.tx,request=self.request)
        self.repo.enqueue_export.assert_not_called();self.repo.find_export.assert_not_called()

    def test_lookup_none_but_enqueue_requires_valid_result(self):
        self.repo.find_export.return_value=None
        self.assertIsNone(self.queue.find_export(self.tx,request=self.request))
        for value in (None,True,object()):
            self.repo.enqueue_export.return_value=value
            with self.assertRaises(AuditExportEnqueueError):self.queue.enqueue_export(self.tx,request=self.request)
        object.__setattr__(self.ref,"job_id",UUID(int=0))
        self.repo.enqueue_export.return_value=self.ref
        with self.assertRaises(AuditExportEnqueueError):self.queue.enqueue_export(self.tx,request=self.request)

    def test_export_namespace_lock_key_stable_signed_integer(self):
        first=_lock_key(self.request.export_id)
        self.assertEqual(first,_lock_key(UUID(str(self.request.export_id))))
        self.assertTrue(-(2**63)<=first<2**63)
        self.assertNotEqual(first,_lock_key(uuid4()))
