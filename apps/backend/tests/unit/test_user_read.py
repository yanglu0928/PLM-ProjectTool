import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock
from plm_assistant.modules.auth.application.user_read import UserReadView, UserGetQuery, UserReadError, AuthorizedUserReadService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


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

    def _assert_read_denied(self, code='AUTH_READ_UNAVAILABLE', entered=True):
        with self.assertRaises(UserReadError) as caught:
            self.service.get(self.query)
        self.assertEqual(str(caught.exception), code)
        self.tx.commit.assert_not_called()
        if entered:
            self.uow.return_value.__exit__.assert_called_once()

    def test_each_dependency_none_refuses_before_uow(self):
        dependencies = dict(unit_of_work=self.uow, access=self.access, repository=self.repo,
                            license_guard=self.guard)
        for field in dependencies:
            with self.subTest(field=field), self.assertRaises(ValueError):
                AuthorizedUserReadService(**(dependencies | {field: None}))
        self.uow.assert_not_called()

    def test_bad_clock_or_clock_fault_never_reads_identity_or_target(self):
        for kind in ('none', 'bool', 'string', 'naive', 'fault'):
            self.setUp()
            if kind == 'fault': self.service._clock = Mock(side_effect=RuntimeError('Synthetic private clock'))
            else:
                values = {'none': None, 'bool': True, 'string': 'Synthetic time', 'naive': datetime.now()}
                self.service._clock = Mock(return_value=values[kind])
            with self.subTest(kind=kind):
                self._assert_read_denied()
                self.access.authorized_admin.assert_not_called()
                self.repo.get.assert_not_called()

    def test_tampered_query_is_rechecked_before_uow(self):
        for field, value in (('session_token', b'x'), ('user_id', True), ('trace_id', None)):
            self.setUp()
            object.__setattr__(self.query, field, value)
            with self.subTest(field=field):
                self._assert_read_denied('VALIDATION_FAILED', entered=False)
                self.uow.assert_not_called()
                self.guard.require_valid.assert_not_called()
                self.repo.get.assert_not_called()

    def test_tampered_view_is_rechecked_and_never_returned(self):
        for field, value in (('username_display', ''), ('account_state', 'DELETED'),
                             ('deployment_role', 'PROJECT_MANAGER'), ('lock_version', True),
                             ('credential_version', 0), ('updated_at', datetime.now())):
            self.setUp()
            object.__setattr__(self.view, field, value)
            with self.subTest(field=field):
                self._assert_read_denied()
                self.assertEqual(self.guard.require_valid.call_count, 1)

    def test_first_or_final_license_denies_with_fixed_error(self):
        for stage in ('first', 'final'):
            self.setUp()
            failure = RuntimeLicenseError('EXPIRED')
            self.guard.require_valid.side_effect = failure if stage == 'first' else [None, failure]
            with self.subTest(stage=stage):
                self._assert_read_denied('LICENSE_OPERATION_DENIED', entered=stage == 'final')
                if stage == 'first':
                    self.uow.assert_not_called()
                    self.repo.get.assert_not_called()
                else:
                    self.repo.get.assert_called_once()

    def test_access_or_uow_fault_has_fixed_error_no_commit(self):
        for kind in ('access', 'enter', 'exit'):
            self.setUp()
            if kind == 'access': self.access.authorized_admin.side_effect = RuntimeError('Synthetic private identity')
            elif kind == 'enter': self.uow.return_value.__enter__.side_effect = RuntimeError('Synthetic private transaction')
            else: self.uow.return_value.__exit__.side_effect = RuntimeError('Synthetic private transaction exit')
            with self.subTest(kind=kind):
                self._assert_read_denied(entered=kind != 'enter')
                if kind != 'exit': self.repo.get.assert_not_called()
