import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.authorized_read import (
    AuthorizedJobReadService,JobGetQuery,JobReadFacts,JobOwnerProjection,JobReadError,
)
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

class JobReadTests(unittest.TestCase):
    def setUp(self):
        self.actor,self.project,self.job,self.trace=uuid4(),uuid4(),uuid4(),uuid4()
        self.tx=SimpleNamespace(commit=Mock())
        @contextmanager
        def uow():yield self.tx
        self.facts=JobReadFacts(self.job,'audit','AUDIT_EXPORT','PROJECT',self.project,self.actor,'PENDING',0,datetime.now(timezone.utc),None)
        self.repo,self.owner,self.guard,self.access,self.admin,self.projects=Mock(),Mock(),Mock(),Mock(),Mock(),Mock()
        self.repo.get.return_value=self.facts
        self.owner.project.return_value=JobOwnerProjection(self.job,False)
        self.access.authenticated_user.return_value=self.actor;self.admin.authorized_admin.return_value=self.actor
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.actor,self.project,'JOB_PROJECT_GET','PROJECT_MANAGER')
        self.service=AuthorizedJobReadService(unit_of_work=uow,project_access=self.access,deployment_access=self.admin,
            projects=self.projects,license_guard=self.guard,repository=self.repo,owners={('audit','AUDIT_EXPORT'):self.owner})
        self.query=JobGetQuery(b'a'*32,self.project,self.trace,self.job)
    def fail(self,code,q=None):
        with self.assertRaises(JobReadError) as cm:self.service.get(q or self.query)
        self.assertEqual(cm.exception.code,code)
        self.tx.commit.assert_not_called()
    def test_real_ports_same_uow_safe_fields_and_no_commit(self):
        value=self.service.get(self.query)
        self.assertEqual(value.facts,self.facts)
        self.assertEqual(self.repo.get.call_count,2)
        self.assertEqual(self.guard.require_valid.call_count,2)
        self.owner.project.assert_called_once_with(self.tx,facts=self.facts,actor_id=self.actor,project_role='PROJECT_MANAGER')
        self.assertNotIn('session_token',repr(self.query))
        for hidden in ('payload_refs','fencing_token','lease_expires_at','worker_ref','idempotency_key'):
            self.assertFalse(hasattr(value.facts,hidden))
        self.tx.commit.assert_not_called()
    def test_invalid_query_does_not_access_ports(self):
        with self.assertRaises(JobReadError) as cm:replace(self.query,session_token=b'x')
        self.assertEqual(cm.exception.code,'VALIDATION_FAILED')
        self.fail('VALIDATION_FAILED',object())
        self.guard.require_valid.assert_not_called();self.repo.get.assert_not_called()
    def test_session_missing_no_lookup(self):
        self.access.authenticated_user.return_value=None
        self.fail('AUTH_ACCESS_DENIED');self.repo.get.assert_not_called()
    def test_admin_cannot_read_project(self):
        self.fail('RESOURCE_NOT_FOUND',replace(self.query,project_id=None))
        self.owner.project.assert_not_called()
    def test_cross_project_and_missing_same_error(self):
        self.repo.get.return_value=replace(self.facts,project_id=uuid4())
        self.fail('RESOURCE_NOT_FOUND')
        self.repo.get.return_value=None;self.fail('RESOURCE_NOT_FOUND')
    def test_customer_only_own_and_im_sees_authorized_other(self):
        self.repo.get.return_value=replace(self.facts,actor_id=uuid4())
        for role in ('CUSTOMER_MANAGER','CUSTOMER_MEMBER'):
            self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.actor,self.project,'JOB_PROJECT_GET',role)
            self.fail('RESOURCE_NOT_FOUND')
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.actor,self.project,'JOB_PROJECT_GET','IMPLEMENTATION_MEMBER')
        self.service.get(self.query)
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.actor,self.project,'JOB_PROJECT_GET','CUSTOMER_MEMBER')
        self.repo.get.return_value=self.facts;self.service.get(self.query)
    def test_bad_owner_wrong_binding_and_changed_facts_fail_closed(self):
        self.owner.project.return_value=JobOwnerProjection(uuid4(),False)
        self.fail('JOB_UNAVAILABLE')
        self.owner.project.return_value=JobOwnerProjection(self.job,False)
        self.repo.get.side_effect=[self.facts,replace(self.facts,state='RUNNING',attempt_count=1)]
        self.fail('JOB_UNAVAILABLE')
    def test_unknown_owner_no_fallback(self):
        self.repo.get.return_value=replace(self.facts,owner_module='unknown')
        self.fail('RESOURCE_NOT_FOUND');self.owner.project.assert_not_called()
    def test_store_and_owner_exception_sanitized(self):
        self.repo.get.side_effect=RuntimeError('sensitive path or SQL')
        self.fail('JOB_UNAVAILABLE')
        self.repo.get.side_effect=None
        self.owner.project.side_effect=RuntimeError('sensitive payload')
        self.fail('JOB_UNAVAILABLE')
    def test_license_refusal_no_store(self):
        self.guard.require_valid.side_effect=RuntimeLicenseError('LICENSE_EXPIRED')
        self.fail('LICENSE_OPERATION_DENIED');self.repo.get.assert_not_called()
    def test_strict_fact_and_projection_shapes(self):
        for changes in ({'attempt_count':True},{'lock_version':True},{'lock_version':-1},{'lock_version':9223372036854775808},{'actor_id':uuid4().__str__()},{'scope':'GLOBAL'}, {'state':'SUCCEEDED'}):
            with self.assertRaises(JobReadError):replace(self.facts,**changes)
        for args in ((self.job,1),(self.job,False,'../../file',uuid4()),(self.job,False,None,uuid4())):
            with self.assertRaises(JobReadError):JobOwnerProjection(*args)

if __name__=='__main__':unittest.main()
