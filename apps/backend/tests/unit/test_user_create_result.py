import unittest
from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_create_result import UserCreateResult, UserCreateResultError


class UserCreateResultTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.view = UserReadView(uuid4(), 'Synthetic first user', 'ENABLED', 'NONE', 1, now, now, 1)
        self.result = UserCreateResult(self.view, uuid4(), uuid4(), uuid4(), uuid4(), now)

    def test_first_safe_fields_and_immutable(self):
        self.assertEqual(self.result.first_view, self.view)
        self.assertEqual(set(self.result.__dataclass_fields__),
            {'first_view','credential_id','actor_id','audit_event_id','trace_id','accepted_at'})
        with self.assertRaises(FrozenInstanceError):
            self.result.actor_id = uuid4()
        for secret in ('password_hash', 'password', 'parameter_set', 'username_normalized'):
            self.assertNotIn(secret, self.result.__dataclass_fields__)

    def test_nonfirst_views_rejected(self):
        for change in ({'account_state':'DISABLED'}, {'deployment_role':'DEPLOYMENT_ADMIN'},
                       {'credential_version':2}, {'lock_version':0}, {'lock_version':2}):
            with self.subTest(change=change), self.assertRaises(UserCreateResultError):
                replace(self.result, first_view=replace(self.view, **change))

    def test_source_ids_exact_nonzero_and_not_self_creator(self):
        for key in ('credential_id','actor_id','audit_event_id','trace_id'):
            for value in (UUID(int=0), str(uuid4()), True, None):
                with self.subTest(key=key,value=value), self.assertRaises(UserCreateResultError):
                    replace(self.result, **{key:value})
        with self.assertRaises(UserCreateResultError):
            replace(self.result, actor_id=self.view.user_id)

    def test_time_type_order_and_safe_errors(self):
        for value in (datetime.now(), self.view.updated_at-timedelta(microseconds=1), 'private date', None):
            with self.assertRaises(UserCreateResultError) as caught:
                replace(self.result, accepted_at=value)
            self.assertEqual(str(caught.exception), 'AUTH_CREATE_RESULT_UNAVAILABLE')
        for value in (object(), None, {'password':'private'}):
            with self.assertRaises(UserCreateResultError):
                replace(self.result, first_view=value)

    def test_rechecks_tampered_nested_view(self):
        object.__setattr__(self.view, 'credential_version', True)
        with self.assertRaises(UserCreateResultError) as caught:
            self.result.__post_init__()
        self.assertEqual(str(caught.exception), 'AUTH_CREATE_RESULT_UNAVAILABLE')
