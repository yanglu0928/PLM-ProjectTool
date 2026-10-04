import unittest
from dataclasses import replace
from datetime import datetime,timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_create import create_user_create_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.managed_user_create import ManagedUserCreateError
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    fail=False
    def validate(self,token,*,csrf_token,require_csrf):
        if self.fail:raise SessionError('AUTH_SESSION_EXPIRED')
        assert len(token)==len(csrf_token)==32 and require_csrf is True


class Writes:
    def __init__(self):
        now=datetime.now(timezone.utc)
        self.view=UserReadView(uuid4(),'Synthetic user','ENABLED','NONE',1,now,now,1)
        self.fail=None;self.passwords=[]
    def create(self,cmd,*,idempotency_key):
        self.passwords.append(cmd.password)
        if self.fail=='unexpected':raise RuntimeError('private password SQL detail')
        if self.fail:raise ManagedUserCreateError(self.fail)
        return self.view


class UserCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.sessions=Sessions();self.writes=Writes()
        self.client=TestClient(create_app(user_create_router=create_user_create_router(
            sessions=self.sessions,writes=self.writes,origins=LoginOriginPolicy(['https://plm.example.test']))),
            base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.headers={'origin':'https://plm.example.test','cookie':'plm_session='+('ab'*32),
            'x-csrf-token':'cd'*32,'idempotency-key':str(uuid4())}
        self.body={'username':'Synthetic user','password':'Synthetic-write-only-value'}
        self.path='/api/v1/admin/users'

    def test_opt_in_first_safe_201_and_current_trace(self):
        with TestClient(create_app()) as bare:self.assertEqual(bare.post(self.path).status_code,404)
        first=self.client.post(self.path,headers=self.headers,json=self.body)
        replay=self.client.post(self.path,headers=self.headers,json=self.body)
        self.assertEqual(first.status_code,201);self.assertEqual(first.json()['data'],replay.json()['data'])
        self.assertNotEqual(first.json()['trace_id'],replay.json()['trace_id'])
        self.assertEqual(set(first.json()['data']),{'user_id','username_display','account_state','deployment_role',
            'credential_version','created_at','updated_at','etag'})
        self.assertEqual(first.headers['etag'],'"v1"')
        self.assertEqual(first.headers['location'],self.path+'/'+str(self.writes.view.user_id))
        self.assertEqual(first.headers['cache-control'],'no-store');self.assertEqual(first.headers['x-content-type-options'],'nosniff')
        self.assertNotIn('set-cookie',first.headers);self.assertNotIn(self.body['password'],first.text)
        self.assertTrue(all(not any(p) for p in self.writes.passwords))

    def test_browser_and_credentials_before_writes(self):
        for field,value,status in (('origin','https://evil.test',403),('host','evil.test',403),
            ('cookie','plm_session=short',401),('x-csrf-token','bad',403),('idempotency-key','short',422)):
            self.assertEqual(self.client.post(self.path,headers=self.headers|{field:value},json=self.body).status_code,status)
        self.sessions.fail=True
        self.assertEqual(self.client.post(self.path,headers=self.headers,json=self.body).status_code,401)
        self.assertEqual(self.writes.passwords,[])

    def test_strict_body_and_password_bytes(self):
        cases=[(b'{"username":"x","password":"a","password":"b"}',400),
            (b'{"username":"x","password":"a","deployment_role":"DEPLOYMENT_ADMIN"}',400),
            (b'{"username":"x","password":NaN}',400),(b'{"username":"x","password":true}',400),
            (b'{"username":"x","password":""}',422),(b'{"username":"x","password":"\\ud800"}',422),
            (b'{"username":"x","password":"a\\u0000b"}',422),(b'\xff',400),(b'x'*16385,400),
            (b'{"username":"x","password":"'+b'x'*1025+b'"}',422)]
        for raw,status in cases:
            r=self.client.post(self.path,headers=self.headers|{'content-type':'application/json'},content=raw)
            self.assertEqual(r.status_code,status);self.assertNotIn('password',r.text)
        self.assertEqual(self.client.post(self.path+'?extra=true',headers=self.headers,json=self.body).status_code,400)
        self.assertEqual(self.client.post(self.path,headers=self.headers|{'content-type':'text/plain'},content='{}').status_code,400)
        self.assertEqual(self.writes.passwords,[])

    def test_duplicate_security_or_content_type_headers_refuse(self):
        for name,status in (('content-type',400),('idempotency-key',422),('origin',403),('x-csrf-token',403)):
            headers=list((self.headers|{'content-type':'application/json'}).items())
            value=dict(headers)[name];headers.append((name,value))
            self.assertEqual(self.client.post(self.path,headers=headers,content='{"username":"x","password":"x"}').status_code,status)
        self.assertEqual(self.writes.passwords,[])

    def test_safe_errors_and_all_paths_clear_password(self):
        for code,status in (('AUTH_ACCESS_DENIED',404),('AUTH_USERNAME_CONFLICT',409),('CONFLICT_IDEMPOTENCY',409),
            ('LICENSE_OPERATION_DENIED',403),('VALIDATION_FAILED',422),('AUTH_CREATE_UNAVAILABLE',503),('unexpected',503)):
            self.writes.fail=code
            r=self.client.post(self.path,headers=self.headers,json=self.body)
            self.assertEqual(r.status_code,status);self.assertNotIn(self.body['password'],r.text)
            self.assertNotIn('private',r.text);self.assertFalse(any(self.writes.passwords[-1]))

    def test_nonfirst_or_wrong_metadata_never_success(self):
        for value in (object(),replace(self.writes.view,account_state='DISABLED'),
            replace(self.writes.view,deployment_role='DEPLOYMENT_ADMIN'),replace(self.writes.view,lock_version=2)):
            self.writes.view=value
            r=self.client.post(self.path,headers=self.headers,json=self.body)
            self.assertEqual(r.status_code,503);self.assertFalse(any(self.writes.passwords[-1]))
