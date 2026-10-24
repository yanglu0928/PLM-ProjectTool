import unittest
from dataclasses import replace
from datetime import datetime,timezone
from uuid import uuid4
from unittest.mock import Mock
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_detail import create_user_detail_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.user_read import UserReadView,UserReadError
from plm_assistant.modules.auth.application.session_service import SessionError


class UserDetailApiTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.view=UserReadView(uuid4(),'用户名称','DISABLED','NONE',7,now,now,12)
        self.sessions=Mock();self.reads=Mock();self.reads.get.return_value=self.view
        self.client=self.enterContext(TestClient(create_app(user_detail_router=create_user_detail_router(
            sessions=self.sessions,reads=self.reads,origins=LoginOriginPolicy(['https://plm.example.test']))),base_url='https://plm.example.test'))
        self.path='/api/v1/admin/users/'+str(self.view.user_id)
        self.headers={'cookie':'plm_session='+(b's'*32).hex()}

    def test_safe_view_real_etag_and_cache_auth_recheck(self):
        r=self.client.get(self.path,headers=self.headers|{'if-none-match':'"v12"'})
        self.assertEqual(r.status_code,200)
        data=r.json()['data']
        self.assertEqual(set(data),{'user_id','username_display','account_state','deployment_role','credential_version','created_at','updated_at','etag'})
        self.assertEqual(data['etag'],r.headers['etag']);self.assertEqual(data['etag'],'"v12"')
        self.assertEqual(data['credential_version'],7)
        self.assertEqual(r.headers['cache-control'],'no-store');self.assertEqual(r.headers['x-content-type-options'],'nosniff')
        self.sessions.validate.assert_called_once_with(b's'*32)
        self.reads.get.assert_called_once()
        self.assertEqual(str(self.reads.get.call_args.args[0].trace_id),r.json()['trace_id'])

    def test_static_owner_error_matrix(self):
        for code,status,public in (('AUTH_ACCESS_DENIED',404,'RESOURCE_NOT_FOUND'),
            ('RESOURCE_NOT_FOUND',404,'RESOURCE_NOT_FOUND'),('LICENSE_OPERATION_DENIED',403,'LICENSE_OPERATION_DENIED'),
            ('AUTH_READ_UNAVAILABLE',503,'SYSTEM_UNAVAILABLE')):
            self.reads.get.side_effect=UserReadError(code)
            r=self.client.get(self.path,headers=self.headers)
            self.assertEqual(r.status_code,status);self.assertEqual(r.json()['error']['code'],public)

    def test_session_failure_never_reads_target(self):
        self.sessions.validate.side_effect=SessionError('AUTH_SESSION_EXPIRED')
        self.assertEqual(self.client.get(self.path,headers=self.headers).status_code,401)
        self.reads.get.assert_not_called()

    def test_invalid_source_and_private_error_are_static(self):
        for value in (object(),replace(self.view,user_id=uuid4())):
            self.reads.get.return_value=value
            self.assertEqual(self.client.get(self.path,headers=self.headers).status_code,503)
        self.reads.get.side_effect=RuntimeError('private SQL')
        r=self.client.get(self.path,headers=self.headers)
        self.assertEqual(r.status_code,503);self.assertNotIn('private',r.text)

    def test_browser_input_boundaries_and_default_closed(self):
        self.assertEqual(self.client.get(self.path).status_code,401)
        self.assertEqual(self.client.get(self.path,headers=self.headers|{'host':'evil.test'}).status_code,403)
        self.assertEqual(self.client.get(self.path+'?password=true',headers=self.headers).status_code,400)
        self.assertEqual(self.client.get('/api/v1/admin/users/not-uuid',headers=self.headers).status_code,422)
        self.assertEqual(self.client.get('/api/v1/admin/users/00000000-0000-0000-0000-000000000000',headers=self.headers).status_code,404)
        self.assertEqual(self.client.post(self.path,headers=self.headers).status_code,405)
        with TestClient(create_app()) as default:self.assertEqual(default.get(self.path).status_code,404)
