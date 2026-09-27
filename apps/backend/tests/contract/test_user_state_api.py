import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_state import create_user_state_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionPrincipal, SessionError
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_state_result import UserStateResult
from plm_assistant.modules.auth.application.user_state import UserStateError


class Sessions:
    def __init__(self, actor):
        now = datetime.now(timezone.utc)
        self.principal = SessionPrincipal(uuid4(), actor, 1, now+timedelta(hours=8), now+timedelta(minutes=30))
        self.fail = None; self.post_fail = None
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        fail = self.fail if require_csrf else self.post_fail
        if fail == 'unexpected': raise RuntimeError('private source')
        if fail: raise SessionError(fail)
        return self.principal


class Writes:
    def __init__(self, actor):
        now = datetime.now(timezone.utc)
        self.view = UserReadView(uuid4(), 'Synthetic state', 'DISABLED', 'NONE', 1, now, now, 2)
        self.actor = actor; self.calls = []; self.fail = None; self.override = None
    def run(self, command, key, operation):
        self.calls.append((command, key, operation))
        if self.fail == 'unexpected': raise RuntimeError('private SQL')
        if self.fail: raise UserStateError(self.fail)
        if self.override is not None: return self.override
        view = replace(self.view, account_state='ENABLED' if operation=='ENABLE' else 'DISABLED')
        return UserStateResult(uuid4(), view, self.actor, uuid4(), uuid4(), operation, 1,
            0 if operation=='ENABLE' else 1, datetime.now(timezone.utc))
    def enable(self, cmd, *, idempotency_key): return self.run(cmd, idempotency_key, 'ENABLE')
    def disable(self, cmd, *, idempotency_key): return self.run(cmd, idempotency_key, 'DISABLE')


class UserStateApiTests(unittest.TestCase):
    def setUp(self):
        actor = uuid4(); self.sessions = Sessions(actor); self.writes = Writes(actor)
        self.client = TestClient(create_app(user_state_router=create_user_state_router(
            sessions=self.sessions, writes=self.writes, origins=LoginOriginPolicy(['https://plm.example.test']))),
            base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.headers = {'origin':'https://plm.example.test', 'cookie':'plm_session='+('ab'*32),
            'x-csrf-token':'cd'*32, 'if-match':'"v1"', 'idempotency-key':str(uuid4())}
        self.path = '/api/v1/admin/users/'+str(self.writes.view.user_id)

    def test_safe_both_operations_default_closed(self):
        with TestClient(create_app()) as bare: self.assertEqual(bare.post(self.path+':disable').status_code,404)
        for op in ('enable', 'disable'):
            r = self.client.post(self.path+':'+op, headers=self.headers)
            self.assertEqual(r.status_code,200); self.assertEqual(r.headers['etag'],'"v2"')
            self.assertEqual(r.headers['cache-control'],'no-store'); self.assertNotIn('set-cookie',r.headers)
            self.assertEqual(r.headers['x-trace-id'],r.json()['trace_id'])
            self.assertEqual(set(r.json()['data']),{'user_id','username_display','account_state','deployment_role',
                'credential_version','created_at','updated_at','etag'})
            self.assertEqual(r.json()['data']['account_state'],'ENABLED' if op=='enable' else 'DISABLED')
            self.assertEqual(self.writes.calls[-1][1],self.headers['idempotency-key'])

    def test_preconditions_no_writes(self):
        for name,value,status in (('origin','https://evil.test',403),('host','evil.test',403),
            ('cookie','plm_session=bad',401),('x-csrf-token','bad',403),('if-match','W/"v1"',400),
            ('if-match','"v01"',400),('idempotency-key','short',422)):
            self.assertEqual(self.client.post(self.path+':disable',headers=self.headers|{name:value}).status_code,status)
        for field,status in (('if-match',428),('idempotency-key',422)):
            self.assertEqual(self.client.post(self.path+':disable',headers={k:v for k,v in self.headers.items() if k!=field}).status_code,status)
        self.assertEqual(self.writes.calls,[])

    def test_strict_empty_body_query_uuid(self):
        for body in (b'{}', b' ', b'null', b'x'*16385):
            self.assertEqual(self.client.post(self.path+':enable',headers=self.headers,content=body).status_code,400)
        self.assertEqual(self.client.post(self.path+':disable?actor=x',headers=self.headers).status_code,400)
        self.assertEqual(self.client.post('/api/v1/admin/users/'+str(UUID(int=0))+':disable',headers=self.headers).status_code,404)
        self.assertEqual(self.writes.calls,[])

    def test_duplicates_rejected(self):
        for name,status in (('origin',403),('cookie',401),('x-csrf-token',403),('if-match',400),('idempotency-key',422)):
            headers=list(self.headers.items())+[(name,self.headers[name])]
            self.assertEqual(self.client.post(self.path+':disable',headers=headers).status_code,status)
        self.assertEqual(self.writes.calls,[])

    def test_static_errors(self):
        for code,status in (('AUTH_ACCESS_DENIED',404),('RESOURCE_NOT_FOUND',404),('CONFLICT_STATE',409),
            ('CONFLICT_VERSION',409),('CONFLICT_IDEMPOTENCY',409),('VALIDATION_FAILED',422),
            ('LICENSE_OPERATION_DENIED',403),('AUTH_STATE_UNAVAILABLE',503),('unexpected',503)):
            self.writes.fail=code; r=self.client.post(self.path+':disable',headers=self.headers)
            self.assertEqual(r.status_code,status);self.assertNotIn('private',r.text)
            if code=='CONFLICT_STATE':self.assertEqual(r.json()['error']['code'],'AUTH_USER_DISABLED')

    def test_self_disable_clear_only_actually_invalid_session(self):
        self.writes.view=replace(self.writes.view,user_id=self.writes.actor)
        path='/api/v1/admin/users/'+str(self.writes.actor)+':disable'
        self.sessions.post_fail='AUTH_SESSION_EXPIRED'
        r=self.client.post(path,headers=self.headers)
        self.assertEqual(r.status_code,200)
        cookie=r.headers['set-cookie']
        for part in ('Max-Age=0','HttpOnly','Secure','SameSite=lax','Path=/'):self.assertIn(part,cookie)
        self.sessions.post_fail=None
        r=self.client.post(path,headers=self.headers)
        self.assertEqual(r.status_code,200);self.assertNotIn('set-cookie',r.headers)
        for failure in ('SYSTEM_UNAVAILABLE','unexpected'):
            self.sessions.post_fail=failure
            self.assertEqual(self.client.post(path,headers=self.headers).status_code,503)

    def test_bad_result_refuses_success(self):
        now=datetime.now(timezone.utc)
        good=UserStateResult(uuid4(),self.writes.view,self.writes.actor,uuid4(),uuid4(),'DISABLE',1,1,now)
        for bad in (object(), replace(good,first_view=replace(good.first_view,user_id=uuid4())),
            replace(good,operation='ENABLE',first_view=replace(good.first_view,account_state='ENABLED'),revoked_session_count=0),
            replace(good,expected_version=2,first_view=replace(good.first_view,lock_version=3))):
            self.writes.override=bad
            self.assertEqual(self.client.post(self.path+':disable',headers=self.headers).status_code,503)
        self.writes.override=None
        self.writes.actor=uuid4()
        self.assertEqual(self.client.post(self.path+':disable',headers=self.headers).status_code,503)

    def test_current_session_failure_before_command(self):
        for fail,status in (('AUTH_SESSION_EXPIRED',401),('AUTH_ACCESS_DENIED',403),('SYSTEM_UNAVAILABLE',503),('unexpected',503)):
            self.sessions.fail=fail
            self.assertEqual(self.client.post(self.path+':disable',headers=self.headers).status_code,status)
        self.assertEqual(self.writes.calls,[])
