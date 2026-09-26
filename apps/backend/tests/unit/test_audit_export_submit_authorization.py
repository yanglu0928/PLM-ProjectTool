from dataclasses import replace,FrozenInstanceError
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from unittest.mock import Mock
import unittest
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.export_submit_authorization import (
    AuditExportSubmitAuthorization,AuditExportSubmitAuthorizationRequest,AuditExportSubmitAuthorizationError,
)
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError


class SubmitAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.now,self.actor,self.project=datetime.now(timezone.utc),uuid4(),uuid4()
        self.tx,self.access,self.admin,self.projects,self.guard=Mock(),Mock(),Mock(),Mock(),Mock()
        self.spec=AuditExportSpec("PROJECT",self.project,"PROJECT_GOVERNANCE",self.now-timedelta(days=1),self.now)
        self.request=AuditExportSubmitAuthorizationRequest(b"s"*32,b"c"*32,uuid4(),self.spec)
        self.access.authenticated_user.return_value=self.actor
        self.admin.authorized_admin.return_value=self.actor
        self.projects.require_in_transaction.side_effect=lambda tx,**kw:AuthorizedProjectAction(self.actor,self.project,kw["operation"],"PROJECT_MANAGER")
        self.service=AuditExportSubmitAuthorization(project_access=self.access,deployment_access=self.admin,projects=self.projects,license_guard=self.guard,clock=lambda:self.now)

    def test_project_same_tx_and_minimal_binding_no_commit(self):
        result=self.service.require_in_transaction(self.tx,request=self.request)
        self.assertEqual((result.actor_id,result.project_id,result.intent_hash),(self.actor,self.project,self.spec.fingerprint()))
        self.access.authenticated_user.assert_called_once_with(self.tx,session_token=b"s"*32,csrf_token=b"c"*32,now=self.now)
        self.projects.require_in_transaction.assert_called_once_with(self.tx,user_id=self.actor,project_id=self.project,operation="AUDIT_PROJECT_EXPORT")
        self.admin.authorized_admin.assert_not_called();self.tx.commit.assert_not_called();self.tx.rollback.assert_not_called()
        self.assertFalse({"session_token","csrf_token","authorized","payload"} & set(result.__dataclass_fields__))
        with self.assertRaises(FrozenInstanceError):result.scope="DEPLOYMENT"
        self.assertNotIn("session_token=",repr(self.request));self.assertNotIn("csrf_token=",repr(self.request))

    def test_deployment_no_project_or_license_recovery_exemption(self):
        request=replace(self.request,spec=replace(self.spec,scope="DEPLOYMENT",project_id=None,purpose="SECURITY_REVIEW"))
        result=self.service.require_in_transaction(self.tx,request=request)
        self.assertEqual(result.scope,"DEPLOYMENT");self.assertIsNone(result.project_id)
        self.guard.require_valid.assert_called_once_with(trace_id=request.trace_id)
        self.projects.require_in_transaction.assert_not_called();self.access.authenticated_user.assert_not_called()

    def test_invalid_inputs_before_guard_or_auth(self):
        for request in (object(),replace(self.request,session_token=b"short"),replace(self.request,csrf_token=b"short"),replace(self.request,trace_id=True),replace(self.request,spec=object())):
            with self.assertRaises(AuditExportSubmitAuthorizationError) as caught:self.service.require_in_transaction(self.tx,request=request)
            self.assertEqual(caught.exception.code,"VALIDATION_FAILED")
        self.guard.require_valid.assert_not_called();self.access.authenticated_user.assert_not_called()

    def test_corrupted_scope_before_guard(self):
        object.__setattr__(self.spec,"project_id",None)
        with self.assertRaises(AuditExportSubmitAuthorizationError) as caught:self.service.require_in_transaction(self.tx,request=self.request)
        self.assertEqual(caught.exception.code,"AUDIT_EXPORT_SCOPE_INVALID")
        self.guard.require_valid.assert_not_called()

    def test_current_actor_and_proof_binding_fail_closed(self):
        for actor in (None,True,uuid4().int):
            self.access.authenticated_user.return_value=actor
            with self.assertRaises(AuditExportSubmitAuthorizationError) as caught:self.service.require_in_transaction(self.tx,request=self.request)
            self.assertEqual(caught.exception.code,"AUTH_ACCESS_DENIED")
        self.access.authenticated_user.return_value=self.actor
        for proof in (True,AuthorizedProjectAction(uuid4(),self.project,"AUDIT_PROJECT_EXPORT","PROJECT_MANAGER"),AuthorizedProjectAction(self.actor,uuid4(),"AUDIT_PROJECT_EXPORT","PROJECT_MANAGER"),AuthorizedProjectAction(self.actor,self.project,"PROJECT_GET","PROJECT_MANAGER"),AuthorizedProjectAction(self.actor,self.project,"AUDIT_PROJECT_EXPORT","IMPLEMENTATION_MEMBER")):
            self.projects.require_in_transaction.side_effect=None;self.projects.require_in_transaction.return_value=proof
            with self.assertRaises(AuditExportSubmitAuthorizationError) as caught:self.service.require_in_transaction(self.tx,request=self.request)
            self.assertEqual(caught.exception.code,"RESOURCE_NOT_FOUND")

    def test_runtime_failures_are_safe_and_no_commit(self):
        for error,code in ((ProjectAuthorizationError("PROJECT_ARCHIVED"),"RESOURCE_NOT_FOUND"),(RuntimeError("synthetic sensitive detail"),"AUDIT_UNAVAILABLE")):
            self.projects.require_in_transaction.side_effect=error
            with self.assertRaises(AuditExportSubmitAuthorizationError) as caught:self.service.require_in_transaction(self.tx,request=self.request)
            self.assertEqual(caught.exception.code,code);self.assertNotIn("sensitive",str(caught.exception))
        self.tx.commit.assert_not_called()

    def test_spec_mutation_by_bad_adapter_rejected(self):
        def bad(tx,**kw):
            object.__setattr__(self.spec,"action","OTHER")
            return AuthorizedProjectAction(self.actor,self.project,kw["operation"],"PROJECT_MANAGER")
        self.projects.require_in_transaction.side_effect=bad
        with self.assertRaises(AuditExportSubmitAuthorizationError) as caught:self.service.require_in_transaction(self.tx,request=self.request)
        self.assertEqual(caught.exception.code,"AUDIT_UNAVAILABLE")
