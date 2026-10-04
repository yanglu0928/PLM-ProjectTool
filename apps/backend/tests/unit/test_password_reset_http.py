import unittest
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.password_reset import create_password_reset_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionPrincipal


class PasswordResetHttpTests(unittest.TestCase):
    def ports(self):
        now=datetime.now(timezone.utc);uid=uuid4()
        principal=SessionPrincipal(uuid4(),uid,1,now+timedelta(hours=8),now+timedelta(minutes=30))
        class Sessions:
            def validate(self,*args,**kwargs):return principal
        class Writes:
            seen=None
            def reset(self,command,**kwargs):self.seen=command;return object()
        writes=Writes();app=create_app(password_reset_router=create_password_reset_router(sessions=Sessions(),writes=writes,
            origins=LoginOriginPolicy(['https://plm.example.test'])))
        headers={'origin':'https://plm.example.test','cookie':'plm_session='+('11'*32),'x-csrf-token':'22'*32,
            'idempotency-key':str(uuid4()),'if-match':'"v1"'}
        return app,writes,headers,'/api/v1/admin/users/'+str(uuid4())+':reset-password'

    def test_unknown_output_no_secrets_erase_buffers(self):
        app,writes,headers,path=self.ports()
        with TestClient(app,base_url='https://plm.example.test') as client:
            response=client.post(path,headers=headers,json={'temporary_password':'Synthetic private password','must_change_password':True})
        self.assertEqual(response.status_code,503);self.assertNotIn('private',response.text)
        self.assertNotIn('set-cookie',response.headers);self.assertFalse(any(writes.seen.password.temporary_password))

    def test_strict_flag_and_surrogate_never_call_service(self):
        app,writes,headers,path=self.ports()
        with TestClient(app,base_url='https://plm.example.test') as client:
            for flag in (False,1,'true',None):
                response=client.post(path,headers=headers,json={'temporary_password':'Synthetic','must_change_password':flag})
                self.assertEqual(response.status_code,422);self.assertIsNone(writes.seen)
            response=client.post(path,headers=headers|{'content-type':'application/json'},
                content=b'{"temporary_password":"\\ud800","must_change_password":true}')
            self.assertEqual(response.status_code,422);self.assertIsNone(writes.seen)

    def test_strong_condition_missing_weak_duplicate_or_multi_reject(self):
        app,writes,headers,path=self.ports();body={'temporary_password':'Synthetic','must_change_password':True}
        with TestClient(app,base_url='https://plm.example.test') as client:
            missing=dict(headers);missing.pop('if-match')
            self.assertEqual(client.post(path,headers=missing,json=body).status_code,428)
            for condition in ('W/"v1"','*','"v1", "v2"','"v01"'):
                self.assertEqual(client.post(path,headers=headers|{'if-match':condition},json=body).status_code,400)
            repeated=list(headers.items())+[('if-match','"v2"')]
            self.assertEqual(client.post(path,headers=repeated,json=body).status_code,400)
        self.assertIsNone(writes.seen)

    def test_default_closed(self):
        with TestClient(create_app()) as client:
            self.assertEqual(client.post('/api/v1/admin/users/'+str(uuid4())+':reset-password').status_code,404)
