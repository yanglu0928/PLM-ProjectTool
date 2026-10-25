from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock
from dataclasses import replace
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.jobs.api.retry import create_job_retry_router
from plm_assistant.modules.jobs.application.retry_request import JobRetryResult, JobRetryError

class RetryApiTests(TestCase):
    def setUp(self):
        self.project,self.source,self.new=uuid4(),uuid4(),uuid4()
        self.sessions,self.retries=Mock(),Mock()
        self.retries.retry.return_value=JobRetryResult(self.source,self.new,self.project,'PROJECT',datetime.now(timezone.utc))
        self.client=TestClient(create_app(job_retry_router=create_job_retry_router(sessions=self.sessions,retries=self.retries,
            origins=LoginOriginPolicy(['https://plm.example.test']))),base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.path=f'/api/v1/projects/{self.project}/jobs/{self.source}:retry'
        self.headers={'origin':'https://plm.example.test','cookie':'plm_session='+(b'a'*32).hex(),
            'x-csrf-token':(b'b'*32).hex(),'idempotency-key':str(uuid4()),'if-match':'"v3"'}
    def post(self,headers=None,**kwargs):
        return self.client.post(self.path,json={},headers=headers or self.headers,**kwargs)

    def test_first_safe_response_and_default_off(self):
        r=self.post();self.assertEqual(r.status_code,202)
        data=r.json()['data']
        self.assertEqual(set(data),{'job_id','source_job_id','scope','project_id','state','etag','status_url','accepted_at'})
        self.assertEqual((data['job_id'],data['source_job_id'],data['state'],data['etag']),(str(self.new),str(self.source),'PENDING','"v0"'))
        self.assertEqual(r.headers['etag'],data['etag']);self.assertEqual(r.headers['location'],data['status_url'])
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertEqual(self.retries.retry.call_args.args[0].expected_version,3)
        with TestClient(create_app()) as default:self.assertEqual(default.post(self.path).status_code,404)

    def test_admin_path_has_no_project_assertion(self):
        self.retries.retry.return_value=replace(self.retries.retry.return_value,project_id=None,scope='DEPLOYMENT')
        r=self.client.post(f'/api/v1/admin/jobs/{self.source}:retry',json={},headers=self.headers)
        self.assertEqual(r.status_code,202);self.assertIsNone(self.retries.retry.call_args.args[0].project_id)
        self.assertEqual(r.json()['data']['status_url'],f'/api/v1/admin/jobs/{self.new}')

    def test_strict_inputs_never_dispatch(self):
        missing=self.headers.copy();del missing['if-match']
        self.assertEqual(self.post(missing).status_code,428)
        for key,value,status in (('if-match','W/"v3"',400),('if-match','*',400),('origin','https://evil.test',403),
            ('cookie','plm_session=bad',401),('x-csrf-token','bad',403),('idempotency-key','short',422)):
            self.assertEqual(self.post(self.headers|{key:value}).status_code,status)
        for raw in (b'',b'[]',b'{"scope":"PROJECT"}',b'{"a":1,"a":2}',b'{"a":NaN}',b'\xff',b'x'*1025):
            self.assertEqual(self.client.post(self.path,content=raw,headers=self.headers|{'content-type':'application/json'}).status_code,400)
        self.assertEqual(self.client.post(self.path+'?x=1',json={},headers=self.headers).status_code,400)
        self.retries.retry.assert_not_called()

    def test_frozen_error_codes_and_bad_result_fail_safe(self):
        for code,status in (('JOB_NOT_RETRYABLE',409),('CONFLICT_VERSION',409),('CONFLICT_IDEMPOTENCY',409),
            ('RESOURCE_NOT_FOUND',404),('LICENSE_OPERATION_DENIED',403),('JOB_UNAVAILABLE',503)):
            self.retries.retry.side_effect=JobRetryError(code)
            r=self.post();self.assertEqual(r.status_code,status)
        self.retries.retry.side_effect=RuntimeError('private SQL/key')
        r=self.post();self.assertEqual(r.status_code,503);self.assertNotIn('private',r.text)
        self.retries.retry.side_effect=None
        self.retries.retry.return_value=JobRetryResult(uuid4(),self.new,self.project,'PROJECT',datetime.now(timezone.utc))
        self.assertEqual(self.post().status_code,503)

    def test_replay_current_validation_and_no_guess_current_state(self):
        one=self.post();two=self.post()
        self.assertEqual(one.json()['data'],two.json()['data'])
        self.assertEqual(self.sessions.validate.call_count,2);self.assertEqual(self.retries.retry.call_count,2)
