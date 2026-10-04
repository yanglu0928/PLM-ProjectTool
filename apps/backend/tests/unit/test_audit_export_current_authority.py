import unittest
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.audit.application.export_contract import AuditExportAuthorityRequest
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthority, AuditExportCurrentAuthorityError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction, ProjectAuthorizationError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class CurrentAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.users,self.projects,self.guard=Mock(),Mock(),Mock()
        self.service=AuditExportCurrentAuthority(users=self.users,projects=self.projects,license_guard=self.guard)
        self.tx=object()
        self.req=AuditExportAuthorityRequest(uuid4(),uuid4(),"PROJECT",uuid4(),"CAPTURE")
        self.users.current_enabled_user.return_value=CurrentUserFacts(self.req.actor_id,"NONE")
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.req.actor_id,self.req.project_id,"AUDIT_PROJECT_EXPORT","PROJECT_MANAGER")

    def deny(self,req,code):
        with self.assertRaises(AuditExportCurrentAuthorityError) as caught:self.service.assert_current(self.tx,request=req)
        self.assertEqual(caught.exception.code,code)

    def test_every_stage_rechecks_without_receiving_session(self):
        for stage in ("CAPTURE","RENDER","PUBLISH"):
            self.assertIsNone(self.service.assert_current(self.tx,request=replace(self.req,stage=stage)))
        self.assertEqual(self.guard.require_valid.call_count,3)
        self.assertEqual(self.users.current_enabled_user.call_count,3)
        self.projects.require_in_transaction.assert_called_with(self.tx,user_id=self.req.actor_id,project_id=self.req.project_id,operation="AUDIT_PROJECT_EXPORT")

    def test_deployment_requires_current_admin(self):
        req=replace(self.req,scope="DEPLOYMENT",project_id=None)
        self.deny(req,"AUTH_ACCESS_DENIED")
        self.users.current_enabled_user.return_value=CurrentUserFacts(req.actor_id,"DEPLOYMENT_ADMIN")
        self.service.assert_current(self.tx,request=req)
        self.projects.require_in_transaction.assert_not_called()

    def test_wrong_user_and_nonfacts_fail(self):
        for facts in (None,True,CurrentUserFacts(uuid4(),"DEPLOYMENT_ADMIN")):
            self.users.current_enabled_user.return_value=facts
            self.deny(self.req,"AUTH_ACCESS_DENIED")
        self.projects.require_in_transaction.assert_not_called()

    def test_admin_not_project_bypass_and_exact_binding(self):
        self.users.current_enabled_user.return_value=CurrentUserFacts(self.req.actor_id,"DEPLOYMENT_ADMIN")
        for proof in (True,AuthorizedProjectAction(uuid4(),self.req.project_id,"AUDIT_PROJECT_EXPORT","PROJECT_MANAGER"),
                      AuthorizedProjectAction(self.req.actor_id,uuid4(),"AUDIT_PROJECT_EXPORT","PROJECT_MANAGER"),
                      AuthorizedProjectAction(self.req.actor_id,self.req.project_id,"PROJECT_GET","PROJECT_MANAGER"),
                      AuthorizedProjectAction(self.req.actor_id,self.req.project_id,"AUDIT_PROJECT_EXPORT","CUSTOMER_MANAGER")):
            self.projects.require_in_transaction.return_value=proof
            self.deny(self.req,"RESOURCE_NOT_FOUND")

    def test_safe_errors_and_license_before_user(self):
        self.guard.require_valid.side_effect=RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        self.deny(self.req,"LICENSE_OPERATION_DENIED")
        self.users.current_enabled_user.assert_not_called()
        self.guard.require_valid.side_effect=None
        self.projects.require_in_transaction.side_effect=ProjectAuthorizationError("PROJECT_ARCHIVED")
        self.deny(self.req,"RESOURCE_NOT_FOUND")
        self.projects.require_in_transaction.side_effect=RuntimeError("unsafe storage detail")
        self.deny(self.req,"AUDIT_UNAVAILABLE")

    def test_invalid_input_and_no_fallback(self):
        self.deny(object(),"VALIDATION_FAILED")
        object.__setattr__(self.req,"stage","OTHER")
        self.deny(self.req,"VALIDATION_FAILED")
        self.guard.require_valid.assert_not_called()
        with self.assertRaises(ValueError):AuditExportCurrentAuthority(users=None,projects=self.projects,license_guard=self.guard)
        for role in (True,"OTHER"):
            with self.assertRaises(ValueError):CurrentUserFacts(uuid4(),role)
