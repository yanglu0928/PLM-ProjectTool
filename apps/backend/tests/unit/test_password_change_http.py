import unittest
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.password_change import create_password_change_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionPrincipal


class PasswordChangeHttpTests(unittest.TestCase):
    def setup_ports(self):
        uid=uuid4();now=datetime.now(timezone.utc)
        principal=SessionPrincipal(uuid4(),uid,1,now+timedelta(hours=8),now+timedelta(minutes=30))
        class Sessions:
            def validate(self,*args,**kwargs):return principal
        class Writes:
            seen=None
            def change(self,command,**kwargs):self.seen=command;return object()
        writes=Writes()
        app=create_app(password_change_router=create_password_change_router(sessions=Sessions(),writes=writes,
            origins=LoginOriginPolicy(['https://plm.example.test'])))
        headers={'origin':'https://plm.example.test','cookie':'plm_session='+('11'*32),
            'x-csrf-token':'22'*32,'idempotency-key':str(uuid4())}
        return app,writes,headers

    def test_unknown_output_fail_closed_and_erase_buffers(self):
        app,writes,headers=self.setup_ports()
        with TestClient(app,base_url='https://plm.example.test') as client:
            r=client.post('/api/v1/auth/password:change',headers=headers,
                json={'current_password':'Synthetic private before','new_password':'Synthetic private after'})
        self.assertEqual(r.status_code,503)
        self.assertNotIn('private',r.text);self.assertNotIn('set-cookie',r.headers)
        self.assertFalse(any(writes.seen.passwords.current_password));self.assertFalse(any(writes.seen.passwords.new_password))

    def test_invalid_json_secret_shape_never_calls_service(self):
        app,writes,headers=self.setup_ports()
        with TestClient(app,base_url='https://plm.example.test') as client:
            for body in ({'current_password':'x','new_password':False},
                {'current_password':'x','new_password':'\x00'},{'current_password':'x','new_password':'y','user_id':'client'}):
                r=client.post('/api/v1/auth/password:change',headers=headers,json=body)
                self.assertIn(r.status_code,(400,422))
                self.assertIsNone(writes.seen)
            r=client.post('/api/v1/auth/password:change',headers=headers|{'content-type':'application/json'},
                content=b'{"current_password":"x","new_password":"\\ud800"}')
            self.assertEqual(r.status_code,422)
            self.assertIsNone(writes.seen)

    def test_default_router_absent(self):
        with TestClient(create_app()) as client:self.assertEqual(client.post('/api/v1/auth/password:change').status_code,404)
