import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_name_patch import create_user_name_patch_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_name_patch import UserNamePatchError
from .test_user_create_api import Sessions


class Writes:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.view = UserReadView(uuid4(), 'Synthetic renamed', 'ENABLED', 'NONE', 1, now, now, 2)
        self.calls = []; self.fail = None
    def patch(self, command):
        self.calls.append(command)
        if self.fail == 'unexpected': raise RuntimeError('Synthetic private SQL')
        if self.fail: raise UserNamePatchError(self.fail)
        return self.view


class UserNamePatchApiTests(unittest.TestCase):
    def setUp(self):
        self.sessions = Sessions(); self.writes = Writes()
        self.client = TestClient(create_app(user_name_patch_router=create_user_name_patch_router(
            sessions=self.sessions, writes=self.writes,
            origins=LoginOriginPolicy(['https://plm.example.test']))), base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.headers = {'origin':'https://plm.example.test', 'cookie':'plm_session='+('ab'*32),
            'x-csrf-token':'cd'*32, 'if-match':'"v1"'}
        self.body = {'username':'Synthetic renamed'}
        self.path = '/api/v1/admin/users/'+str(self.writes.view.user_id)

    def test_opt_in_safe_response_no_key(self):
        with TestClient(create_app()) as bare: self.assertEqual(bare.patch(self.path).status_code,404)
        r = self.client.patch(self.path, headers=self.headers, json=self.body)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['etag'],'"v2"')
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertEqual(r.headers['x-content-type-options'],'nosniff')
        self.assertNotIn('set-cookie',r.headers)
        self.assertEqual(set(r.json()['data']),{'user_id','username_display','account_state','deployment_role',
            'credential_version','created_at','updated_at','etag'})
        self.assertEqual(self.writes.calls[0].expected_version,1)
        self.assertEqual(str(self.writes.calls[0].trace_id),r.json()['trace_id'])
        self.assertEqual(self.writes.calls[0].username,self.body['username'])

    def test_noop_safe_same_etag(self):
        self.writes.view=replace(self.writes.view,lock_version=1)
        r=self.client.patch(self.path,headers=self.headers,json=self.body)
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers['etag'],'"v1"')

    def test_security_preconditions_before_write(self):
        for field,value,status in (('origin','https://evil.test',403),('host','evil.test',403),
            ('cookie','plm_session=short',401),('x-csrf-token','bad',403),
            ('if-match','W/"v1"',400),('if-match','*',400),('if-match','"v01"',400),
            ('if-match','"v9223372036854775807"',400)):
            self.assertEqual(self.client.patch(self.path,headers=self.headers|{field:value},json=self.body).status_code,status)
        self.assertEqual(self.client.patch(self.path,headers={k:v for k,v in self.headers.items() if k!='if-match'},json=self.body).status_code,428)
        self.sessions.fail=True
        self.assertEqual(self.client.patch(self.path,headers=self.headers,json=self.body).status_code,401)
        self.assertEqual(self.writes.calls,[])

    def test_strict_input(self):
        for raw in (b'{}',b'{"username":"a","username":"b"}',b'{"username":NaN}',
                    b'{"username":true}',b'{"username":"x","deployment_role":"DEPLOYMENT_ADMIN"}',
                    b'{"username":"x","username_normalized":"x"}',b'\xff',b'x'*16385):
            self.assertEqual(self.client.patch(self.path,headers=self.headers|{'content-type':'application/json'},content=raw).status_code,400)
        self.assertEqual(self.client.patch(self.path+'?extra=true',headers=self.headers,json=self.body).status_code,400)
        self.assertEqual(self.client.patch(self.path,headers=self.headers|{'content-type':'text/plain'},content='{}').status_code,400)
        self.assertEqual(self.client.patch('/api/v1/admin/users/'+str(UUID(int=0)),headers=self.headers,json=self.body).status_code,404)
        self.assertEqual(self.writes.calls,[])

    def test_duplicate_headers(self):
        for name,status in (('content-type',400),('if-match',400),('origin',403),('x-csrf-token',403)):
            headers=list((self.headers|{'content-type':'application/json'}).items())
            headers.append((name,dict(headers)[name]))
            self.assertEqual(self.client.patch(self.path,headers=headers,content='{"username":"x"}').status_code,status)
        self.assertEqual(self.writes.calls,[])

    def test_static_error_mapping(self):
        for code,status in (('AUTH_ACCESS_DENIED',404),('RESOURCE_NOT_FOUND',404),('CONFLICT_VERSION',409),
            ('CONFLICT_DUPLICATE',409),('LICENSE_OPERATION_DENIED',403),('VALIDATION_FAILED',422),
            ('AUTH_PATCH_UNAVAILABLE',503),('unexpected',503)):
            self.writes.fail=code
            r=self.client.patch(self.path,headers=self.headers,json=self.body)
            self.assertEqual(r.status_code,status);self.assertNotIn('private',r.text)

    def test_bad_result_no_success(self):
        original=self.writes.view
        for view in (object(),replace(original,user_id=uuid4()),replace(original,lock_version=5)):
            self.writes.view=view
            self.assertEqual(self.client.patch(self.path,headers=self.headers,json=self.body).status_code,503)
