"""HTTP fault ports only; real commit/history evidence lives in PG validators."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.password_change import create_password_change_router
from plm_assistant.modules.auth.api.password_reset import create_password_reset_router
from plm_assistant.modules.auth.application.password_change_result import PasswordChangeResult
from plm_assistant.modules.auth.application.password_reset_result import PasswordResetResult
from plm_assistant.modules.auth.application.session_service import SessionPrincipal, SessionError
from plm_assistant.modules.platform.application.errors import ApplicationError

DEFAULT = object()


class PasswordHttpDefensiveTests(unittest.TestCase):
    def request(self, kind, *, initial=DEFAULT, post=DEFAULT, write=DEFAULT, result_fault=None,
                content_type='application/json', zero_target=False):
        now = datetime.now(timezone.utc)
        uid = uuid4()
        principal = SessionPrincipal(uuid4(), uid, 1, now + timedelta(hours=8), now + timedelta(minutes=30))
        target = UUID(int=0) if zero_target else uid
        def output(value):
            if isinstance(value, Exception): raise value
            return value
        class Sessions:
            def validate(self, *args, **kwargs):
                value = initial if kwargs.get('require_csrf') else post
                if value is DEFAULT: value = principal
                if value == 'wrong-user': value = replace(principal, user_id=uuid4())
                if value == 'zero-user': value = replace(principal, user_id=UUID(int=0))
                if value == 'string-user': value = replace(principal, user_id=str(uid))
                return output(value)
        class Writes:
            seen = None
            def execute(self, command, **kwargs):
                self.seen = command
                if write is not DEFAULT: return output(write)
                values = dict(result_id=uuid4(), user_id=target, before_credential_id=uuid4(),
                    credential_id=uuid4(), before_credential_version=1, credential_version=2,
                    before_user_version=1, user_version=2, audit_event_id=uuid4(), trace_id=uuid4(),
                    revoked_session_count=1, changed_at=now, accepted_at=now)
                if kind == 'reset': values.update(actor_id=uid, target_state='ENABLED')
                if result_fault == 'user': values['user_id'] = uuid4()
                if result_fault == 'actor': values['actor_id'] = uuid4()
                if result_fault == 'version': values.update(before_user_version=2, user_version=3)
                result = (PasswordResetResult if kind == 'reset' else PasswordChangeResult)(**values)
                if result_fault == 'tampered': object.__setattr__(result, 'credential_version', 999)
                return result
            change = execute
            reset = execute
        writes = Writes()
        origins = LoginOriginPolicy(['https://plm.example.test'])
        if kind == 'reset':
            app = create_app(password_reset_router=create_password_reset_router(sessions=Sessions(), writes=writes, origins=origins))
            path = '/api/v1/admin/users/' + str(target) + ':reset-password'
            body = {'temporary_password': 'Synthetic private temporary', 'must_change_password': True}
        else:
            app = create_app(password_change_router=create_password_change_router(sessions=Sessions(), writes=writes, origins=origins))
            path = '/api/v1/auth/password:change'
            body = {'current_password': 'Synthetic private original', 'new_password': 'Synthetic private new'}
        headers = {'origin': 'https://plm.example.test', 'cookie': 'plm_session=' + '11' * 32,
                   'x-csrf-token': '22' * 32, 'idempotency-key': str(uuid4()),
                   'if-match': '"v1"', 'content-type': content_type}
        with TestClient(app, base_url='https://plm.example.test') as client:
            response = client.post(path, headers=headers, json=body)
        self.assertNotIn('private', response.text)
        if writes.seen is not None:
            proof = writes.seen.password if kind == 'reset' else writes.seen.passwords
            buffers = (proof.temporary_password,) if kind == 'reset' else (proof.current_password, proof.new_password)
            self.assertTrue(all(not any(value) for value in buffers))
        return response, writes

    def test_missing_dependencies_refuse_router_construction(self):
        for factory in (create_password_change_router, create_password_reset_router):
            for missing in ('sessions', 'writes', 'origins'):
                with self.subTest(factory=factory.__name__, missing=missing):
                    values = dict(sessions=object(), writes=object(), origins=object()); values[missing] = None
                    with self.assertRaises(ValueError): factory(**values)

    def test_untrusted_initial_principal_never_calls_write(self):
        for kind in ('reset', 'change'):
            for value in (None, object(), 'zero-user', 'string-user'):
                with self.subTest(kind=kind, value=type(value).__name__):
                    response, writes = self.request(kind, initial=value)
                    self.assertEqual(response.status_code, 503)
                    self.assertIsNone(writes.seen)
                    self.assertNotIn('set-cookie', response.headers)

    def test_initial_unknown_and_safe_application_failures_do_not_write(self):
        for kind in ('reset', 'change'):
            for failure in (RuntimeError('private initial failure'), ApplicationError('SYSTEM_UNAVAILABLE')):
                response, writes = self.request(kind, initial=failure)
                self.assertEqual(response.status_code, 503)
                self.assertIsNone(writes.seen)
                self.assertNotIn('set-cookie', response.headers)

    def test_result_mismatch_and_invalid_frozen_dto_refuse_success(self):
        for kind in ('reset', 'change'):
            for fault in (('user', 'actor', 'version', 'tampered') if kind == 'reset' else ('user', 'tampered')):
                with self.subTest(kind=kind, fault=fault):
                    response, writes = self.request(kind, result_fault=fault)
                    self.assertEqual(response.status_code, 503)
                    self.assertIsNotNone(writes.seen)
                    self.assertNotIn('set-cookie', response.headers)

    def test_unknown_write_exception_erases_and_hides_details(self):
        for kind in ('reset', 'change'):
            response, writes = self.request(kind, write=RuntimeError('private write failure'))
            self.assertEqual(response.status_code, 503)
            self.assertIsNotNone(writes.seen)
            self.assertNotIn('set-cookie', response.headers)

    def test_postwrite_untrusted_identity_never_guesses_cookie_expiry(self):
        for kind in ('reset', 'change'):
            for value in (None, object(), 'wrong-user', RuntimeError('private final failure'),
                          SessionError('AUTH_SESSION_UNAVAILABLE'), ApplicationError('SYSTEM_UNAVAILABLE')):
                with self.subTest(kind=kind, value=type(value).__name__):
                    response, writes = self.request(kind, post=value)
                    self.assertEqual(response.status_code, 503)
                    self.assertIsNotNone(writes.seen)
                    self.assertNotIn('set-cookie', response.headers)

    def test_only_confirmed_expired_session_clears_cookie(self):
        for kind in ('reset', 'change'):
            response, _ = self.request(kind, post=SessionError('AUTH_SESSION_EXPIRED'))
            self.assertEqual(response.status_code, 200)
            cookie = response.headers['set-cookie'].lower()
            for attribute in ('max-age=0', 'secure', 'httponly', 'samesite=lax', 'path=/'):
                self.assertIn(attribute, cookie)
            response, _ = self.request(kind)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('set-cookie', response.headers)

    def test_wrong_content_type_and_zero_target_never_write(self):
        for kind in ('reset', 'change'):
            response, writes = self.request(kind, content_type='text/plain')
            self.assertEqual(response.status_code, 400)
            self.assertIsNone(writes.seen)
        response, writes = self.request('reset', zero_target=True)
        self.assertEqual(response.status_code, 404)
        self.assertIsNone(writes.seen)
