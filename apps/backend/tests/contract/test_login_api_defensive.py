"""HTTP refusal and allocated password-buffer erasure, not real login SQL."""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login import create_login_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.login_service import LoginError
from plm_assistant.modules.auth.application.session_service import IssuedSession
from plm_assistant.modules.auth.application.session_view import LoginSessionView


class LoginApiDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.origins = LoginOriginPolicy(['https://plm.example.test'])
        self.uid, self.token = uuid4(), b't' * 32
        now = datetime.now(timezone.utc)
        self.issued = IssuedSession(uuid4(), self.uid, self.token, b'c' * 32,
                                    now + timedelta(hours=8), now + timedelta(minutes=30))
        self.headers = {'origin': 'https://plm.example.test', 'content-type': 'application/json'}
        self.body = {'username': 'Synthetic user', 'password': 'Synthetic private password'}

    def client(self, *, source='normal'):
        self.login, self.views = Mock(), Mock()
        self.login.login.return_value = self.issued
        self.views.resolve_for_session.return_value = LoginSessionView(self.uid, 'Synthetic user', 'NONE', ())
        app = create_app(login_router=create_login_router(login=self.login, views=self.views, origins=self.origins))
        async def controlled(scope, receive, send):
            if scope['type'] == 'http' and source != 'normal':
                scope = dict(scope, client=None if source == 'missing' else ('', 50000))
            await app(scope, receive, send)
        client = TestClient(controlled, base_url='https://plm.example.test', raise_server_exceptions=False)
        self.addCleanup(client.close)
        return client

    def assert_safe(self, response, status, code):
        self.assertEqual(response.status_code, status)
        payload = response.json()
        self.assertEqual(payload['error']['code'], code)
        UUID(payload['trace_id'])
        self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertNotIn('Synthetic private', response.text)
        self.assertNotIn(self.token.hex(), response.text)

    def test_each_login_dependency_required(self):
        dependencies = dict(login=Mock(), views=Mock(), origins=self.origins)
        for field in dependencies:
            with self.subTest(field=field), self.assertRaises(ValueError):
                create_login_router(**(dependencies | {field: None}))

    def test_bad_json_content_type_and_field_types_never_call_service(self):
        cases = ((b'{}', 'text/plain'), (b'{', 'application/json'), (b'\xff', 'application/json'),
                 (b'[]', 'application/json'), (b'{"username":1,"password":"x"}', 'application/json'),
                 (b'{"username":"x","password":1}', 'application/json'))
        for index, (body, content_type) in enumerate(cases):
            client = self.client()
            with self.subTest(case=index):
                self.assert_safe(client.post('/api/v1/auth/login', content=body,
                    headers=self.headers | {'content-type': content_type}), 400, 'REQUEST_MALFORMED')
                self.login.login.assert_not_called()
                self.views.resolve_for_session.assert_not_called()

    def test_isolated_unicode_surrogates_refuse_before_service(self):
        for encoded in (b'\\ud800', b'\\udfff'):
            client = self.client()
            with self.subTest(encoded=encoded):
                self.assert_safe(client.post('/api/v1/auth/login',
                    content=b'{"username":"x","password":"' + encoded + b'"}',
                    headers=self.headers), 401, 'AUTH_INVALID_CREDENTIALS')
                self.login.login.assert_not_called()
                self.views.resolve_for_session.assert_not_called()

    def test_missing_client_and_empty_host_erase_allocated_buffer(self):
        for source in ('missing', 'empty'):
            client = self.client(source=source)
            allocated = []
            def allocate(value):
                buffer = bytearray(value)
                allocated.append(buffer)
                return buffer
            with self.subTest(source=source), patch(
                'plm_assistant.modules.auth.api.login.bytearray', side_effect=allocate, create=True
            ):
                self.assert_safe(client.post('/api/v1/auth/login', json=self.body,
                    headers=self.headers), 503, 'SYSTEM_UNAVAILABLE')
            self.assertEqual(len(allocated), 1)
            self.assertEqual(allocated[0], bytearray(len(self.body['password'].encode())))
            self.login.login.assert_not_called()
            self.views.resolve_for_session.assert_not_called()

    def test_service_fixed_and_generic_faults_erase_password_no_cookie(self):
        cases = ((LoginError('AUTH_INVALID_CREDENTIALS'), 401, 'AUTH_INVALID_CREDENTIALS'),
                 (LoginError('AUTH_RATE_LIMITED'), 429, 'AUTH_RATE_LIMITED'),
                 (LoginError('SYSTEM_UNAVAILABLE'), 503, 'SYSTEM_UNAVAILABLE'),
                 (RuntimeError('Synthetic private service failure'), 500, 'SYSTEM_INTERNAL'))
        for failure, status, code in cases:
            client = self.client()
            self.login.login.side_effect = failure
            with self.subTest(code=code):
                self.assert_safe(client.post('/api/v1/auth/login', json=self.body,
                                            headers=self.headers), status, code)
                attempt = self.login.login.call_args.args[0]
                self.assertEqual(attempt.password, bytearray(len(self.body['password'].encode())))
                self.views.resolve_for_session.assert_not_called()

    def test_projection_identity_public_flag_and_source_fail_without_cookie(self):
        for kind in ('identity', 'public_flag', 'source'):
            client = self.client()
            if kind == 'identity':
                self.views.resolve_for_session.return_value = LoginSessionView(uuid4(), 'Synthetic user', 'NONE', ())
            elif kind == 'public_flag':
                self.views.resolve_for_session.return_value = LoginSessionView(self.uid, 'Synthetic user', 'NONE', (), 1)
            else:
                self.views.resolve_for_session.side_effect = RuntimeError('Synthetic private projection failure')
            with self.subTest(kind=kind):
                self.assert_safe(client.post('/api/v1/auth/login', json=self.body,
                    headers=self.headers), 503, 'SYSTEM_UNAVAILABLE')
                self.views.resolve_for_session.assert_called_once_with(user_id=self.uid, session_token=self.token)
                attempt = self.login.login.call_args.args[0]
                self.assertEqual(attempt.password, bytearray(len(self.body['password'].encode())))
