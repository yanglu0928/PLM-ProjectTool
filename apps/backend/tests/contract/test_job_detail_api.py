from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import UUID,uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.jobs.api.read_detail import create_job_detail_router
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts,JobOwnerProjection,JobDetail,JobReadError

class JobDetailApiTests(TestCase):
    def setUp(self):
        self.job,self.project,self.actor=uuid4(),uuid4(),uuid4()
        self.facts=JobReadFacts(self.job,'audit','AUDIT_EXPORT','PROJECT',self.project,self.actor,'PENDING',0,datetime.now(timezone.utc),None,7)
        self.reader=Mock();self.reader.get.return_value=JobDetail(self.facts,JobOwnerProjection(self.job,False))
        self.client=TestClient(create_app(job_detail_router=create_job_detail_router(reads=self.reader,
            origins=LoginOriginPolicy(['https://plm.example.test']))),base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.path=f'/api/v1/projects/{self.project}/jobs/{self.job}'
        self.cookie='plm_session='+(b'j'*32).hex()
    def get(self,path=None,**headers):return self.client.get(path or self.path,headers={'cookie':self.cookie,**headers})
    def test_projection_and_real_version_default_closed(self):
        with TestClient(create_app()) as default:self.assertEqual(default.get(self.path).status_code,404)
        response=self.get();self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['etag'],'"v7"');self.assertEqual(response.headers['cache-control'],'no-store')
        data=response.json()['data']
        self.assertEqual(set(data),{'job_id','job_type','owner_module','scope','project_id','state','progress','checkpoint',
            'attempt_count','retryable','error_code','result_ref','created_at','completed_at','etag'})
        self.assertIsNone(data['progress']);self.assertIsNone(data['error_code'])
        self.assertNotIn('actor_id',data);self.assertNotIn('payload',response.text)
        self.assertEqual(self.reader.get.call_args.args[0].session_token,b'j'*32)
    def test_admin_scope_and_result_reference(self):
        end=self.facts.created_at
        facts=replace(self.facts,scope='DEPLOYMENT',project_id=None,state='SUCCEEDED',completed_at=end,lock_version=8)
        result=uuid4();self.reader.get.return_value=JobDetail(facts,JobOwnerProjection(self.job,False,'AUDIT_EXPORT',result))
        response=self.get(f'/api/v1/admin/jobs/{self.job}')
        self.assertEqual(response.status_code,200);self.assertEqual(response.headers['etag'],'"v8"')
        self.assertEqual(response.json()['data']['result_ref'],{'type':'AUDIT_EXPORT','id':str(result)})
    def test_invalid_requests_do_not_call_reader(self):
        for path,headers,status in ((self.path+'?payload=x',{},400),(self.path,{'host':'evil.test'},403),
            (self.path,{'origin':'https://evil.test'},403),(self.path,{'cookie':'plm_session=bad'},401),
            (self.path,{'cookie':self.cookie+'; '+self.cookie},401),
            (f'/api/v1/projects/{self.project}/jobs/{UUID(int=0)}',{},404)):
            with self.subTest(path=path,headers=headers):self.assertEqual(self.get(path,**headers).status_code,status)
        self.reader.get.assert_not_called()
    def test_safe_errors_and_binding_refusal(self):
        for error,status in ((JobReadError('AUTH_ACCESS_DENIED'),401),(JobReadError('RESOURCE_NOT_FOUND'),404),
            (JobReadError('LICENSE_OPERATION_DENIED'),403),(RuntimeError('private SQL/password path'),503)):
            self.reader.get.side_effect=error;response=self.get()
            self.assertEqual(response.status_code,status);self.assertNotIn('private',response.text)
            self.assertEqual(set(response.json()),{'error','trace_id'})
        self.reader.get.side_effect=None
        self.reader.get.return_value=JobDetail(replace(self.facts,project_id=uuid4()),JobOwnerProjection(self.job,False))
        self.assertEqual(self.get().status_code,503)
    def test_conditionals_never_skip_current_reader(self):
        self.assertEqual(self.get(**{'if-none-match':'"v7"'}).status_code,200)
        self.reader.get.assert_called_once()
        self.reader.get.side_effect=JobReadError('AUTH_ACCESS_DENIED')
        self.assertEqual(self.get(**{'if-none-match':'"v7"'}).status_code,401)
