import unittest
from datetime import datetime,timezone
from uuid import uuid4
from unittest.mock import Mock
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_list import create_user_list_router
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.user_list import UserListPage
from plm_assistant.modules.auth.application.user_read import UserReadView,UserReadError
from plm_assistant.modules.auth.application.session_service import SessionError


class UserListApiTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc);self.view=UserReadView(uuid4(),'安全用户','DISABLED','NONE',3,now,now,8)
        self.sessions=Mock();self.reads=Mock();self.codec=UserListCursorCodec(b'u'*32)
        self.reads.list.return_value=UserListPage((self.view,),True,(now,self.view.user_id))
        self.client=self.enterContext(TestClient(create_app(user_list_router=create_user_list_router(sessions=self.sessions,
            reads=self.reads,origins=LoginOriginPolicy(['https://plm.example.test']),cursors=self.codec)),base_url='https://plm.example.test'))
        self.headers={'cookie':'plm_session='+(b's'*32).hex()};self.path='/api/v1/admin/users'
    def test_safe_page_cursor_and_etag(self):
        r=self.client.get(self.path,params={'page_size':1},headers=self.headers)
        self.assertEqual(r.status_code,200);data=r.json()['data']
        self.assertEqual(set(data),{'items','next_cursor','has_more'})
        self.assertEqual(set(data['items'][0]),{'user_id','username_display','account_state','deployment_role','credential_version','created_at','updated_at','etag'})
        self.assertEqual(data['items'][0]['etag'],'"v8"');self.assertTrue(data['has_more'])
        q=self.reads.list.call_args.args[0]
        self.assertEqual(self.codec.decode(data['next_cursor'],query=q),(self.view.created_at,self.view.user_id))
        self.assertEqual(r.headers['cache-control'],'no-store');self.assertEqual(r.headers['x-content-type-options'],'nosniff')
    def test_empty_last_page(self):
        self.reads.list.return_value=UserListPage((),False)
        data=self.client.get(self.path,headers=self.headers).json()['data']
        self.assertEqual(data,{'items':[],'has_more':False,'next_cursor':None})
    def test_errors_and_unknown_source_safe(self):
        for error,status,code in ((UserReadError('AUTH_ACCESS_DENIED'),404,'RESOURCE_NOT_FOUND'),
            (UserReadError('LICENSE_OPERATION_DENIED'),403,'LICENSE_OPERATION_DENIED'),
            (RuntimeError('private SQL'),503,'SYSTEM_UNAVAILABLE')):
            self.reads.list.side_effect=error;r=self.client.get(self.path,headers=self.headers)
            self.assertEqual(r.status_code,status);self.assertEqual(r.json()['error']['code'],code);self.assertNotIn('private',r.text)
        self.reads.list.side_effect=None;self.reads.list.return_value=object()
        self.assertEqual(self.client.get(self.path,headers=self.headers).status_code,503)
    def test_session_failure_no_page_read(self):
        self.sessions.validate.side_effect=SessionError('AUTH_SESSION_EXPIRED')
        self.assertEqual(self.client.get(self.path,headers=self.headers).status_code,401)
        self.reads.list.assert_not_called()
    def test_query_browser_and_default_closed(self):
        for query,status in (('?page_size=0',422),('?page_size=201',422),('?page_size=01',422),
            ('?page_size=1&page_size=1',400),('?state=ENABLED',400),('?cursor=invalid',400)):
            self.assertEqual(self.client.get(self.path+query,headers=self.headers).status_code,status)
        self.assertEqual(self.client.get(self.path).status_code,401)
        self.assertEqual(self.client.get(self.path,headers=self.headers|{'host':'evil.test'}).status_code,403)
        self.assertEqual(self.client.post(self.path,headers=self.headers).status_code,405)
        with TestClient(create_app()) as default:self.assertEqual(default.get(self.path).status_code,404)
