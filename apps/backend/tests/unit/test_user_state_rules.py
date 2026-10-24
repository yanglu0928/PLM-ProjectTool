import unittest
from dataclasses import replace, FrozenInstanceError
from datetime import datetime,timezone,timedelta
from uuid import UUID,uuid4
from plm_assistant.modules.auth.domain.user_state import decide_user_state,UserStateRuleError
from plm_assistant.modules.auth.application.user_state_result import UserStateResult,UserStateResultError
from plm_assistant.modules.auth.application.user_read import UserReadView


class UserStateRulesTests(unittest.TestCase):
    def setUp(self):
        self.facts=dict(operation='DISABLE',state='ENABLED',deployment_role='NONE',credential_version=1,
            has_active_credential=True,lock_version=1,expected_version=1,other_enabled_admins=0)
    def test_enable_disable_exact(self):
        disable=decide_user_state(**self.facts)
        self.assertEqual((disable.before_state,disable.after_state,disable.next_version,
            disable.revoke_all_sessions,disable.audit_action),('ENABLED','DISABLED',2,True,'USER_DISABLED'))
        enable=decide_user_state(**(self.facts|dict(operation='ENABLE',state='DISABLED')))
        self.assertEqual((enable.after_state,enable.revoke_all_sessions,enable.audit_action),('ENABLED',False,'USER_ENABLED'))
        with self.assertRaises(FrozenInstanceError): disable.next_version=7
    def test_state_and_version_no_fake_noop(self):
        for change,code in ((dict(state='DISABLED'),'CONFLICT_STATE'),
            (dict(expected_version=0),'CONFLICT_VERSION'),
            (dict(lock_version=2**63-1,expected_version=2**63-1),'CONFLICT_VERSION')):
            with self.assertRaises(UserStateRuleError) as caught:decide_user_state(**(self.facts|change))
            self.assertEqual(caught.exception.code,code)
    def test_last_admin_protection_without_blanket_admin_or_self_ban(self):
        with self.assertRaises(UserStateRuleError) as caught:
            decide_user_state(**(self.facts|dict(deployment_role='DEPLOYMENT_ADMIN')))
        self.assertEqual(caught.exception.code,'CONFLICT_STATE')
        result=decide_user_state(**(self.facts|dict(deployment_role='DEPLOYMENT_ADMIN',other_enabled_admins=1)))
        self.assertEqual(result.after_state,'DISABLED')
    def test_zero_credential_cannot_enable(self):
        with self.assertRaises(UserStateRuleError) as caught:
            decide_user_state(**(self.facts|dict(operation='ENABLE',state='DISABLED',
                credential_version=0,has_active_credential=False)))
        self.assertEqual(caught.exception.code,'CONFLICT_STATE')
    def test_bad_types_and_corrupt_source(self):
        for change in (dict(other_enabled_admins=True),dict(expected_version=True),dict(credential_version=-1),
            dict(lock_version=2**63),dict(operation='UNKNOWN'),dict(state='UNKNOWN'),dict(has_active_credential=1)):
            with self.assertRaises(UserStateRuleError) as caught:decide_user_state(**(self.facts|change))
            self.assertEqual(caught.exception.code,'VALIDATION_FAILED')
        for change in (dict(has_active_credential=False),dict(credential_version=0)):
            with self.assertRaises(UserStateRuleError) as caught:decide_user_state(**(self.facts|change))
            self.assertEqual(caught.exception.code,'AUTH_STATE_UNAVAILABLE')


class UserStateResultTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc);self.user=uuid4()
        view=UserReadView(self.user,'Synthetic first disabled','DISABLED','NONE',1,now,now,2)
        self.result=UserStateResult(uuid4(),view,uuid4(),uuid4(),uuid4(),'DISABLE',1,2,now)
    def test_exact_shape_immutable_self_source_possible(self):
        self.assertEqual(replace(self.result,actor_id=self.user).actor_id,self.user)
        with self.assertRaises(FrozenInstanceError):self.result.operation='ENABLE'
        for forbidden in ('password_hash','password','username_normalized','session_token'):
            self.assertNotIn(forbidden,self.result.__dataclass_fields__)
    def test_strict_types_versions_states_and_times(self):
        for change in (dict(result_id=UUID(int=0)),dict(actor_id=UUID(int=0)),dict(trace_id=UUID(int=0)),
            dict(operation='ENABLE'),dict(expected_version=True),dict(expected_version=0),dict(expected_version=2**63-1),
            dict(revoked_session_count=True),dict(revoked_session_count=-1),dict(revoked_session_count=2**63),
            dict(accepted_at=self.result.accepted_at.replace(tzinfo=None)),
            dict(accepted_at=self.result.accepted_at-timedelta(seconds=1)),dict(first_view=object())):
            with self.subTest(change=change),self.assertRaises(UserStateResultError):replace(self.result,**change)
    def test_enable_requires_zero_count_nonzero_credential(self):
        view=replace(self.result.first_view,account_state='ENABLED')
        enabled=replace(self.result,first_view=view,operation='ENABLE',revoked_session_count=0)
        self.assertEqual(enabled.first_view.account_state,'ENABLED')
        with self.assertRaises(UserStateResultError):replace(enabled,revoked_session_count=1)
        with self.assertRaises(UserStateResultError):
            replace(self.result,first_view=replace(self.result.first_view,credential_version=0))
    def test_nested_tampered_view_rechecked(self):
        object.__setattr__(self.result.first_view,'lock_version',False)
        with self.assertRaises(UserStateResultError): self.result.__post_init__()
