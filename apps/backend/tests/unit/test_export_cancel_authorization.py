from dataclasses import replace
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization,AuditExportCancelAuthorizationRequest
from plm_assistant.modules.audit.application.export_submit_authorization import AuditExportSubmitAuthorizationError
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class CancelAuthorizationTests(TestCase):
    def setUp(self):
        self.actor,self.project=uuid4(),uuid4();now=datetime.now(timezone.utc)
        self.spec=AuditExportSpec('PROJECT',self.project,'PROJECT_GOVERNANCE',now-timedelta(hours=1),now)
        self.c=AuditExportCancelAuthorizationRequest(b'a'*32,b'b'*32,uuid4(),self.spec,self.actor)
        self.access,self.admin,self.projects,self.guard,self.tx=Mock(),Mock(),Mock(),Mock(),Mock()
        self.access.authenticated_user.return_value=self.actor;self.admin.authorized_admin.return_value=self.actor
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.actor,self.project,'AUDIT_PROJECT_CANCEL','IMPLEMENTATION_MEMBER')
        self.service=AuditExportCancelAuthorization(project_access=self.access,deployment_access=self.admin,projects=self.projects,license_guard=self.guard)

    def test_creator_or_current_manager_exact_project(self):
        self.assertEqual(self.service.require_in_transaction(self.tx,request=self.c).actor_id,self.actor)
        with self.assertRaises(AuditExportSubmitAuthorizationError):self.service.require_in_transaction(self.tx,request=replace(self.c,original_actor_id=uuid4()))
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.actor,self.project,'AUDIT_PROJECT_CANCEL','PROJECT_MANAGER')
        self.service.require_in_transaction(self.tx,request=replace(self.c,original_actor_id=uuid4()))
        self.tx.commit.assert_not_called()

    def test_malformed_proof_does_not_grant_creator_bypass(self):
        original=self.projects.require_in_transaction.return_value
        for value in (None,replace(original,project_id=uuid4()),replace(original,operation='PROJECT_GET'),replace(original,project_role='UNKNOWN')):
            self.projects.require_in_transaction.return_value=value
            with self.assertRaises(AuditExportSubmitAuthorizationError):self.service.require_in_transaction(self.tx,request=self.c)

    def test_validation_before_dependencies(self):
        for c in (True,replace(self.c,session_token=b'a'),replace(self.c,original_actor_id=True),replace(self.c,trace_id=None)):
            with self.assertRaises(AuditExportSubmitAuthorizationError):self.service.require_in_transaction(self.tx,request=c)
        self.guard.require_valid.assert_not_called();self.access.authenticated_user.assert_not_called()

    def test_deployment_admin_license_and_safe_failure(self):
        spec=replace(self.spec,scope='DEPLOYMENT',project_id=None,purpose='SECURITY_REVIEW')
        self.service.require_in_transaction(self.tx,request=replace(self.c,spec=spec,original_actor_id=uuid4()))
        self.projects.require_in_transaction.assert_not_called();self.admin.authorized_admin.assert_called_once()
        self.guard.require_valid.side_effect=RuntimeError('private value')
        with self.assertRaises(AuditExportSubmitAuthorizationError) as cm:self.service.require_in_transaction(self.tx,request=self.c)
        self.assertEqual(str(cm.exception),'AUDIT_UNAVAILABLE')
