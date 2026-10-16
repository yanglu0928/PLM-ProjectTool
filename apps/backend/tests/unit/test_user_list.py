import unittest
from dataclasses import replace
from datetime import datetime,timedelta
from uuid import uuid4
from unittest.mock import Mock
from . import test_user_read as read_tests
from plm_assistant.modules.auth.application.user_list import UserListQuery,UserListPage,AuthorizedUserListService
from plm_assistant.modules.auth.application.user_read import UserReadError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


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

    def _deny_list(self, code='AUTH_READ_UNAVAILABLE', entered=True):
        with self.assertRaises(UserReadError) as caught:
            self.service.list(self.query)
        self.assertEqual(caught.exception.code, code)
        self.tx.commit.assert_not_called()
        if entered:
            self.uow.return_value.__exit__.assert_called_once()

    def test_all_dependencies_none_refuse_before_transaction(self):
        deps = dict(unit_of_work=self.uow, access=self.access, repository=self.repo, license_guard=self.guard)
        for field in deps:
            with self.subTest(field=field), self.assertRaises(ValueError):
                AuthorizedUserListService(**(deps | {field: None}))
        self.uow.assert_not_called()

    def test_invalid_clock_or_clock_fault_refuses_before_identity_and_page(self):
        for kind in ('none', 'bool', 'string', 'naive', 'fault'):
            self.setUp()
            if kind == 'fault':
                self.service._clock = Mock(side_effect=RuntimeError('Synthetic private clock'))
            else:
                value = {'none': None, 'bool': True, 'string': 'Synthetic time', 'naive': datetime.now()}[kind]
                self.service._clock = Mock(return_value=value)
            with self.subTest(kind=kind):
                self._deny_list()
                self.access.authorized_admin.assert_not_called()
                self.repo.list.assert_not_called()

    def test_tampered_query_refuses_before_guard_and_transaction(self):
        for field, value in (('session_token', b'x'), ('trace_id', None), ('page_size', True), ('before', [])):
            self.setUp()
            object.__setattr__(self.query, field, value)
            with self.subTest(field=field):
                self._deny_list('VALIDATION_FAILED', entered=False)
                self.uow.assert_not_called()
                self.guard.require_valid.assert_not_called()
                self.repo.list.assert_not_called()

    def test_tampered_page_is_revalidated_never_returned(self):
        for field, value in (('items', []), ('items', (object(),)), ('has_more', 1),
                             ('next_position', None), ('items', (self.view, self.view))):
            self.setUp()
            object.__setattr__(self.page, field, value)
            with self.subTest(field=field, value_type=type(value).__name__):
                self._deny_list()
                self.assertEqual(self.guard.require_valid.call_count, 1)

    def test_first_and_final_license_refuse_with_fixed_code(self):
        for stage in ('first', 'final'):
            self.setUp()
            fault = RuntimeLicenseError('EXPIRED')
            self.guard.require_valid.side_effect = fault if stage == 'first' else [None, fault]
            with self.subTest(stage=stage):
                self._deny_list('LICENSE_OPERATION_DENIED', entered=stage == 'final')
                if stage == 'first':
                    self.uow.assert_not_called()
                    self.repo.list.assert_not_called()
                else:
                    self.repo.list.assert_called_once()

    def test_access_and_transaction_faults_fixed_no_commit(self):
        for kind in ('access', 'enter', 'exit'):
            self.setUp()
            if kind == 'access': self.access.authorized_admin.side_effect = RuntimeError('Synthetic private identity')
            elif kind == 'enter': self.uow.return_value.__enter__.side_effect = RuntimeError('Synthetic private UOW enter')
            else: self.uow.return_value.__exit__.side_effect = RuntimeError('Synthetic private UOW exit')
            with self.subTest(kind=kind):
                self._deny_list(entered=kind != 'enter')
                if kind != 'exit': self.repo.list.assert_not_called()
