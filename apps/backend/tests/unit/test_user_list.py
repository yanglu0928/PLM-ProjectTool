import unittest
from dataclasses import replace
from datetime import datetime,timedelta
from uuid import uuid4
from . import test_user_read as read_tests
from plm_assistant.modules.auth.application.user_list import UserListQuery,UserListPage,AuthorizedUserListService
from plm_assistant.modules.auth.application.user_read import UserReadError


class UserListTests(unittest.TestCase):
    def setUp(self):
        read_tests.UserReadTests.setUp(self)
        self.query=UserListQuery(b's'*32,uuid4(),1)
        self.page=UserListPage((self.view,),True,(self.view.created_at,self.view.user_id))
        self.repo.list.return_value=self.page
        self.service=AuthorizedUserListService(unit_of_work=self.uow,access=self.access,repository=self.repo,license_guard=self.guard)

    def test_current_page_no_commit_or_secret_query(self):
        self.assertEqual(self.service.list(self.query),self.page)
        self.repo.list.assert_called_once_with(self.tx,page_size=1,before=None)
        self.tx.commit.assert_not_called();self.assertEqual(self.guard.require_valid.call_count,2)
        self.assertNotIn('session_token=',repr(self.query));self.assertNotIn('next_position=',repr(self.page))

    def test_no_admin_never_reads_page(self):
        self.access.authorized_admin.return_value=None
        with self.assertRaises(UserReadError) as caught:self.service.list(self.query)
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED');self.repo.list.assert_not_called()

    def test_invalid_queries(self):
        for changes in ({'page_size':True},{'page_size':0},{'page_size':201},{'before':(datetime.now(),uuid4())},
            {'before':[]},{'session_token':b's'}):
            with self.assertRaises(UserReadError):replace(self.query,**changes)
        with self.assertRaises(UserReadError):self.service.list(object())

    def test_page_sort_duplicates_and_next_shape(self):
        other=replace(self.view,user_id=uuid4(),created_at=self.view.created_at-timedelta(seconds=1))
        for args in (((self.view,self.view),False,None),((other,self.view),False,None),
            ((),True,(self.view.created_at,self.view.user_id)),((self.view,),False,(self.view.created_at,self.view.user_id)),
            ((object(),),False,None)):
            with self.assertRaises(UserReadError):UserListPage(*args)

    def test_repo_boundary_and_page_size_binding(self):
        q=replace(self.query,before=(self.view.created_at,self.view.user_id))
        with self.assertRaises(UserReadError):self.service.list(q)
        self.repo.list.return_value=UserListPage((self.view,),True,(self.view.created_at,self.view.user_id))
        with self.assertRaises(UserReadError):self.service.list(replace(self.query,page_size=2))
        self.repo.list.return_value=object()
        with self.assertRaises(UserReadError):self.service.list(self.query)

    def test_empty_page_and_faults_static(self):
        self.repo.list.return_value=UserListPage((),False)
        self.assertEqual(self.service.list(self.query).items,())
        self.repo.list.side_effect=RuntimeError('private SQL')
        with self.assertRaises(UserReadError) as caught:self.service.list(self.query)
        self.assertEqual(str(caught.exception),'AUTH_READ_UNAVAILABLE')
        self.repo.list.side_effect=None;self.guard.require_valid.side_effect=[None,RuntimeError('private guard')]
        with self.assertRaises(UserReadError):self.service.list(self.query)
        self.tx.commit.assert_not_called()
