import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock
from plm_assistant.modules.auth.application.user_read import UserReadView, UserGetQuery, UserReadError, AuthorizedUserReadService


class UserReadTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.view=UserReadView(uuid4(),'Synthetic user','ENABLED','NONE',1,now,now,1)
        self.query=UserGetQuery(b's'*32,self.view.user_id,uuid4())
        self.tx=Mock();self.uow=Mock();self.uow.return_value.__enter__=Mock(return_value=self.tx)
        self.uow.return_value.__exit__=Mock(return_value=False)
        self.access=Mock();self.access.authorized_admin.return_value=uuid4()
        self.repo=Mock();self.repo.get.return_value=self.view;self.guard=Mock()
        self.service=AuthorizedUserReadService(unit_of_work=self.uow,access=self.access,repository=self.repo,license_guard=self.guard)

    def test_current_admin_and_safe_fields_no_commit(self):
        self.assertEqual(self.service.get(self.query),self.view)
        self.access.authorized_admin.assert_called_once()
        self.repo.get.assert_called_once_with(self.tx,user_id=self.query.user_id)
        self.assertEqual(self.guard.require_valid.call_count,2)
        self.tx.commit.assert_not_called()
        self.assertNotIn('session_token=',repr(self.query))
        self.assertEqual(set(self.view.__dataclass_fields__),{'user_id','username_display','account_state',
            'deployment_role','credential_version','created_at','updated_at','lock_version'})

    def test_denied_current_admin_never_reads_target(self):
        for value in (None,True,'admin'):
            self.access.authorized_admin.return_value=value
            with self.assertRaises(UserReadError) as caught:self.service.get(self.query)
            self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED')
        self.repo.get.assert_not_called();self.tx.commit.assert_not_called()

    def test_missing_target_and_wrong_binding(self):
        self.repo.get.return_value=None
        with self.assertRaises(UserReadError) as caught:self.service.get(self.query)
        self.assertEqual(caught.exception.code,'RESOURCE_NOT_FOUND')
        for value in (object(),replace(self.view,user_id=uuid4())):
            self.repo.get.return_value=value
            with self.assertRaises(UserReadError):self.service.get(self.query)

    def test_disabled_target_is_admin_visible(self):
        self.repo.get.return_value=replace(self.view,account_state='DISABLED',credential_version=0)
        self.assertEqual(self.service.get(self.query).account_state,'DISABLED')

    def test_invalid_view_and_query(self):
        for changes in ({'lock_version':True},{'credential_version':-1},{'username_display':''},
            {'account_state':'DELETED'},{'deployment_role':'PROJECT_MANAGER'},
            {'updated_at':self.view.created_at-timedelta(seconds=1)},{'created_at':datetime.now()}):
            with self.assertRaises(UserReadError):replace(self.view,**changes)
        with self.assertRaises(UserReadError):replace(self.query,session_token=b'x')
        with self.assertRaises(UserReadError):self.service.get(object())

    def test_repo_fault_and_final_guard_fault_static_no_commit(self):
        self.repo.get.side_effect=RuntimeError('private query')
        with self.assertRaises(UserReadError) as caught:self.service.get(self.query)
        self.assertEqual(str(caught.exception),'AUTH_READ_UNAVAILABLE')
        self.repo.get.side_effect=None;self.guard.require_valid.side_effect=[None,RuntimeError('private guard')]
        with self.assertRaises(UserReadError):self.service.get(self.query)
        self.tx.commit.assert_not_called()
