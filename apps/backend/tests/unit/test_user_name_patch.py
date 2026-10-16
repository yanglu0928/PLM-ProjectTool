import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.auth.application.user_name_patch import (
    PatchUserName, UserNamePatchService, UserNamePatchError)
from plm_assistant.modules.auth.application.user_read import UserReadView


class UserNamePatchTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.user = uuid4(), uuid4()
        self.cmd = PatchUserName(b't'*32, b'c'*32, uuid4(), self.user, 1, '  新姓名-e\u0301  ')
        now = datetime.now(timezone.utc)
        self.view = UserReadView(self.user, '新姓名-é', 'ENABLED', 'NONE', 1, now, now, 2)
        self.tx = SimpleNamespace(commit=Mock())
        @contextmanager
        def uow():
            yield self.tx
        self.access = Mock(); self.access.authorized_admin.return_value = self.actor
        self.repo = Mock(); self.repo.patch.return_value = (self.view, True)
        self.guard = Mock(); self.audit = Mock(); self.audit.append.return_value = uuid4()
        self.service = UserNamePatchService(unit_of_work=uow, access=self.access,
            repository=self.repo, audit=self.audit, license_guard=self.guard)

    def test_changed_safe_audit_and_final_authority(self):
        self.assertEqual(self.service.patch(self.cmd), self.view)
        self.tx.commit.assert_called_once()
        self.assertEqual(self.guard.require_valid.call_count, 2)
        self.assertEqual(self.access.authorized_admin.call_count, 2)
        draft = self.audit.append.call_args.args[1]
        self.assertEqual(draft.action, 'USER_NAME_CHANGED')
        self.assertEqual(draft.target_object_id, self.user)
        self.assertNotIn(self.view.username_display, repr(draft))
        self.assertEqual(self.repo.patch.call_args.kwargs['username'].normalized, '新姓名-é')

    def test_noop_no_commit_or_audit(self):
        self.repo.patch.return_value = (replace(self.view, lock_version=1), False)
        self.service.patch(self.cmd)
        self.tx.commit.assert_not_called(); self.audit.append.assert_not_called()

    def test_validation_before_dependencies(self):
        for change in ({'expected_version':True}, {'expected_version':-1},
                       {'expected_version':2**63}, {'username':'\x00'},
                       {'username':None}, {'session_token':b'x'}, {'user_id':uuid4().hex}):
            with self.subTest(change=change), self.assertRaises(UserNamePatchError) as caught:
                self.service.patch(replace(self.cmd, **change))
            self.assertEqual(caught.exception.code, 'VALIDATION_FAILED')
        self.guard.require_valid.assert_not_called(); self.repo.patch.assert_not_called()

    def test_final_access_changed_or_lost_no_commit(self):
        for final in (None, uuid4()):
            self.access.authorized_admin.side_effect = [self.actor, final]
            with self.assertRaises(UserNamePatchError) as caught:
                self.service.patch(self.cmd)
            self.assertEqual(caught.exception.code, 'AUTH_ACCESS_DENIED')
        self.tx.commit.assert_not_called()

    def test_dependency_faults_static(self):
        for component, method in ((self.repo,'patch'), (self.audit,'append'),
                                  (self.guard,'require_valid'), (self.tx,'commit')):
            getattr(component, method).side_effect = RuntimeError('Synthetic private source')
            with self.assertRaises(UserNamePatchError) as caught:
                self.service.patch(self.cmd)
            self.assertEqual(str(caught.exception), 'AUTH_PATCH_UNAVAILABLE')
            getattr(component, method).side_effect = None

    def test_wrong_result_rejected(self):
        for result in ((replace(self.view, user_id=uuid4()), True),
                       (replace(self.view, lock_version=3), True), (self.view, 1), (None, True)):
            self.repo.patch.return_value = result
            with self.assertRaises(UserNamePatchError): self.service.patch(self.cmd)
        self.tx.commit.assert_not_called()

    def test_missing_deps_and_error_sanitization(self):
        with self.assertRaises(ValueError):
            UserNamePatchService(unit_of_work=None, access=self.access, repository=self.repo,
                audit=self.audit, license_guard=self.guard)
        self.assertEqual(str(UserNamePatchError('private detail')), 'AUTH_PATCH_UNAVAILABLE')
