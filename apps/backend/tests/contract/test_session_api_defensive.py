"""HTTP error contracts only; mocked Ports are not real Session/SQL evidence."""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from unittest.mock import Mock

from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    create_session_read_router, create_session_renew_router, create_session_logout_router)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionPrincipal
from plm_assistant.modules.auth.application.session_view import LoginSessionView


class SessionApiDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.uid, self.token = uuid4(), b's' * 32
        now = datetime.now(timezone.utc)
        self.principal = SessionPrincipal(uuid4(), self.uid, 1,
            now + timedelta(hours=8), now + timedelta(minutes=30))
        self.origins = LoginOriginPolicy(['https://plm.example.test'])
        self.headers = {'origin': 'https://plm.example.test', 'cookie': 'plm_session=' + self.token.hex(),
                        'x-csrf-token': (b'c' * 32).hex(), 'idempotency-key': 'Synthetic-key-123'}

    def client(self):
        self.sessions, self.views = Mock(), Mock()
        self.sessions.validate.return_value = self.principal
        self.views.resolve_for_session.return_value = LoginSessionView(self.uid, 'Synthetic user', 'NONE', ())
        app = create_app(
            session_router=create_session_read_router(sessions=self.sessions, views=self.views, origins=self.origins),
            session_renew_router=create_session_renew_router(sessions=self.sessions, views=self.views, origins=self.origins),
            session_logout_router=create_session_logout_router(sessions=self.sessions, origins=self.origins))
        client = TestClient(app, base_url='https://plm.example.test')
        self.addCleanup(client.close)
        return client

    def assert_safe(self, response, status=503, code='SYSTEM_UNAVAILABLE'):
        self.assertEqual(response.status_code, status)
        payload = response.json()
        self.assertEqual(set(payload), {'error', 'trace_id'})
        self.assertEqual(payload['error']['code'], code)
        UUID(payload['trace_id'])
        self.assertNotIn('set-cookie', response.headers)
        self.assertNotIn('Synthetic private', response.text)
        self.assertNotIn(self.token.hex(), response.text)

    def test_each_router_requires_actual_dependencies(self):
        for factory in (create_session_read_router, create_session_renew_router, create_session_logout_router):
            dependencies = dict(sessions=Mock(), origins=self.origins)
            if factory is not create_session_logout_router:
                dependencies['views'] = Mock()
            for field in dependencies:
                with self.subTest(factory=factory.__name__, field=field), self.assertRaises(ValueError):
                    factory(**(dependencies | {field: None}))

    def test_read_validate_and_projection_faults_have_no_cookie(self):
        for kind in ('validate', 'identity', 'source', 'public_flag'):
            client = self.client()
            if kind == 'validate': self.sessions.validate.side_effect = RuntimeError('Synthetic private validation')
            elif kind == 'identity':
                self.views.resolve_for_session.return_value = LoginSessionView(uuid4(), 'Synthetic user', 'NONE', ())
            elif kind == 'source': self.views.resolve_for_session.side_effect = RuntimeError('Synthetic private projection')
            else: self.views.resolve_for_session.return_value = LoginSessionView(self.uid, 'Synthetic user', 'NONE', (), 1)
            with self.subTest(kind=kind):
                self.assert_safe(client.get('/api/v1/auth/session', headers=self.headers))
                if kind == 'validate': self.views.resolve_for_session.assert_not_called()
                else: self.views.resolve_for_session.assert_called_once_with(user_id=self.uid, session_token=self.token)
                self.sessions.renew.assert_not_called()

    def test_renew_validate_faults_do_not_project_or_rotate(self):
        for failure, status, code in (
            (SessionError('AUTH_ACCESS_DENIED'), 403, 'AUTH_CSRF_INVALID'),
            (SessionError('SYSTEM_UNAVAILABLE'), 503, 'SYSTEM_UNAVAILABLE'),
            (SessionError('AUTH_SESSION_EXPIRED'), 401, 'AUTH_SESSION_EXPIRED'),
            (RuntimeError('Synthetic private validation'), 503, 'SYSTEM_UNAVAILABLE')):
            client = self.client()
            self.sessions.validate.side_effect = failure
            with self.subTest(code=code, exception=type(failure).__name__):
                self.assert_safe(client.post('/api/v1/auth/session:renew', headers=self.headers), status, code)
                self.views.resolve_for_session.assert_not_called()
                self.sessions.renew.assert_not_called()

    def test_renew_projection_faults_never_rotate(self):
        for kind in ('identity', 'source', 'public_flag'):
            client = self.client()
            if kind == 'identity':
                self.views.resolve_for_session.return_value = LoginSessionView(uuid4(), 'Synthetic user', 'NONE', ())
            elif kind == 'source': self.views.resolve_for_session.side_effect = RuntimeError('Synthetic private projection')
            else: self.views.resolve_for_session.return_value = LoginSessionView(self.uid, 'Synthetic user', 'NONE', (), 1)
            with self.subTest(kind=kind):
                self.assert_safe(client.post('/api/v1/auth/session:renew', headers=self.headers))
                self.sessions.renew.assert_not_called()

    def test_renew_service_faults_after_good_projection_never_set_cookie(self):
        for failure, status, code in (
            (SessionError('AUTH_ACCESS_DENIED'), 403, 'AUTH_CSRF_INVALID'),
            (SessionError('SYSTEM_UNAVAILABLE'), 503, 'SYSTEM_UNAVAILABLE'),
            (SessionError('AUTH_SESSION_EXPIRED'), 401, 'AUTH_SESSION_EXPIRED'),
            (RuntimeError('Synthetic private renewal'), 503, 'SYSTEM_UNAVAILABLE')):
            client = self.client()
            self.sessions.renew.side_effect = failure
            with self.subTest(code=code, exception=type(failure).__name__):
                self.assert_safe(client.post('/api/v1/auth/session:renew', headers=self.headers), status, code)
                self.views.resolve_for_session.assert_called_once_with(user_id=self.uid, session_token=self.token)
                self.sessions.renew.assert_called_once()

    def test_logout_non_exact_true_never_clears_cookie(self):
        for value in (False, None, 1, 'yes'):
            client = self.client()
            self.sessions.logout.return_value = value
            with self.subTest(result_type=type(value).__name__):
                self.assert_safe(client.post('/api/v1/auth/logout', headers=self.headers))
                self.sessions.logout.assert_called_once()

    def test_logout_service_faults_have_fixed_errors_and_no_cookie(self):
        for failure, status, code in (
            (SessionError('AUTH_ACCESS_DENIED'), 403, 'AUTH_CSRF_INVALID'),
            (SessionError('SYSTEM_UNAVAILABLE'), 503, 'SYSTEM_UNAVAILABLE'),
            (RuntimeError('Synthetic private logout'), 503, 'SYSTEM_UNAVAILABLE')):
            client = self.client()
            self.sessions.logout.side_effect = failure
            with self.subTest(code=code, exception=type(failure).__name__):
                self.assert_safe(client.post('/api/v1/auth/logout', headers=self.headers), status, code)
                self.sessions.logout.assert_called_once()
