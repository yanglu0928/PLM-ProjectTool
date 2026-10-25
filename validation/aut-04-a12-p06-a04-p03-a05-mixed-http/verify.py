"""Actual configured Windows reset/change mixed requests; aggregate evidence only."""
import argparse
import asyncio
import json
import math
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Lock
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.entrypoints.password_capacity import get_process_password_capacity
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings

spec = spec_from_file_location('_mixed_http_source', Path(__file__).resolve().parents[1] /
                              'aut-04-a12-p06-a01-password-concurrency' / 'verify.py')
b = module_from_spec(spec)
spec.loader.exec_module(b)
OUTCOME = []


def exercise(v, settings, *, slots):
    # Validate real Bootstrap input, not model_copy or a substituted legacy gate.
    settings = BootstrapSettings(**(settings.model_dump() | {'password_kdf_slots': slots}))
    assert settings.password_kdf_slots == slots
    budget = get_process_password_capacity(slots=slots)
    m = b.m
    hasher = m.ScryptPasswordHasher()
    sessions = m.SessionService(unit_of_work=v['uow'], repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher), audit=v['audit'], idempotency=m.SqlAlchemyIdempotencyReceipts())
    def issue(uid, password):
        return sessions.issue(user_id=uid, trace_id=uuid4(), proof=m.PasswordIssueProof(bytearray(password.encode())))
    def headers(session=None):
        return {'origin': b.ORIGIN, 'cookie': 'plm_session=' + (v['tokens'][1] if session is None else session.token).hex(),
                'x-csrf-token': (m.fixture.base.auth.CSRF if session is None else session.csrf_token).hex(),
                'idempotency-key': str(uuid4())}
    errors = []
    real_runtime = prod.create_database_runtime
    def runtime(url):
        value = real_runtime(url)
        event.listen(value._engine, 'handle_error', lambda ctx: errors.append(getattr(ctx.original_exception, 'sqlstate', None)))
        return value
    with patch.object(prod, 'create_database_runtime', side_effect=runtime):
        app = prod.create_production_platform_write_app(settings)
    old, temporary, normal = 'Synthetic mixed original', 'Synthetic mixed temporary', 'Synthetic mixed normal'
    lock = Lock()
    active = peak = calls = 0
    real_hash, real_verify = m.ScryptPasswordHasher.hash_password, m.ScryptPasswordHasher.verify_password
    def tracked(method):
        def run(self, *args, **kwargs):
            nonlocal active, peak, calls
            with lock:
                active += 1; calls += 1; peak = max(peak, active)
                assert active <= budget.snapshot()['active'] <= slots
            try:
                return method(self, *args, **kwargs)
            finally:
                with lock: active -= 1
        return run
    reports = []
    def measure(name, requests):
        nonlocal peak, calls
        peak = calls = 0
        with patch.object(m.ScryptPasswordHasher, 'hash_password', tracked(real_hash)), \
             patch.object(m.ScryptPasswordHasher, 'verify_password', tracked(real_verify)):
            rows = asyncio.run(b.batch(app, requests))
        times = sorted(t for t, _ in rows)
        report = {'group': name, 'slots': slots, 'samples': 20,
                  'successes': sum(response.status_code == 200 for _, response in rows),
                  'p95_ms': round(times[math.ceil(.95 * len(times)) - 1], 3),
                  'limit_ms': 1000, 'actual_kdf_calls': calls, 'actual_kdf_peak': peak,
                  'final_active': budget.snapshot()['active'], 'sql_errors': len(errors)}
        report['performance_pass'] = report['successes'] == 20 and times[math.ceil(.95 * len(times)) - 1] <= 1000
        reports.append(report)
        print('MIXED_PASSWORD_HTTP ' + json.dumps(report, sort_keys=True))
        assert report['successes'] == 20 and calls == 30 and 0 < peak <= slots
        assert active == 0 and budget.snapshot()['active'] == 0 and not errors
        return [response for _, response in rows]
    with TestClient(app, base_url=b.ORIGIN) as client:
        users, old_sessions = [], []
        for i in range(20):
            response = client.post('/api/v1/admin/users', headers=headers(),
                                   json={'username': f'Synthetic mixed user {i}', 'password': old})
            assert response.status_code == 201
            uid = UUID(response.json()['data']['user_id'])
            users.append(uid); old_sessions.append(issue(uid, old))
        resets = [('POST', f'/api/v1/admin/users/{uid}:reset-password', headers() | {'if-match': '"v1"'},
                   {'temporary_password': temporary, 'must_change_password': True}) for uid in users[:10]]
        changes = [('POST', '/api/v1/auth/password:change', headers(session),
                    {'current_password': old, 'new_password': normal}) for session in old_sessions[10:]]
        firsts = measure('mixed_fresh', resets + changes)
        for uid, session, response in zip(users, old_sessions, firsts, strict=True):
            assert response.json()['data'] == {'credential_version': 2}
            row = v['db'].execute('SELECT credential_version,lock_version FROM plm.auth_users WHERE user_id=%s', (uid,)).fetchone()
            assert tuple(row) == (2, 2)
            try: sessions.validate(session.token)
            except SessionError as exc: assert exc.code == 'AUTH_SESSION_EXPIRED'
            else: raise AssertionError('Old Session survived mixed write')
        current = [issue(uid, normal) for uid in users[10:]]
        histories = resets + [(method, path, h | {'cookie': 'plm_session=' + fresh.token.hex(),
                      'x-csrf-token': fresh.csrf_token.hex()}, body)
                     for (method, path, h, body), fresh in zip(changes, current, strict=True)]
        tables = ('auth_users', 'auth_password_credentials', 'auth_sessions', 'auth_user_create_results',
                  'auth_user_state_results', 'auth_password_change_results', 'auth_password_reset_results',
                  'aud_events', 'plt_idempotency_receipts')
        def snapshot():
            return {table: tuple(v['db'].execute('SELECT * FROM plm.' + table + ' ORDER BY 1')) for table in tables}
        before = snapshot()
        replayed = measure('mixed_history', histories)
        for i, (first, response) in enumerate(zip(firsts, replayed, strict=True)):
            assert response.json()['data'] == first.json()['data']
            if i < 10: assert response.headers['etag'] == first.headers['etag']
        assert snapshot() == before
    OUTCOME.append(all(report['performance_pass'] for report in reports))
    print('PASS mixed actual Windows HTTP functional/integrity: 10 reset+10 change, fresh/history each30 trueKDF, '
          'shared total bounded/final0, firsts retained/history nine tables unchanged/old Sessions expired. '
          'Synthetic trust; ASGI in-process, not network/TLS/production or package proof.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--slots', type=int, choices=(4, 8, 16), default=4)
    args = parser.parse_args()
    # The outer fixture also constructs real write factories. Bind its Bootstrap
    # to the same capacity from the very first factory in this process.
    with patch.dict(os.environ, {'PLM_PASSWORD_KDF_SLOTS': str(args.slots)}):
        b.windows.http.m.fixture.main(exercise=lambda v: b.windows.exercise(v, extra=lambda v, s: exercise(v, s, slots=args.slots)))
    if OUTCOME != [True]:
        raise SystemExit('MIXED_PASSWORD_HTTP FAIL: original 1000ms acceptance retained')
