from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.jobs.api.cancel import create_project_job_cancel_router
from plm_assistant.modules.jobs.application.cancel_request import JobCancelResult,JobCancelError

class ProjectJobCancelApiTests(TestCase):
    def setUp(self):
        self.job,self.project=uuid4(),uuid4();self.sessions,self.cancel=Mock(),Mock()
        self.cancel.cancel.return_value=JobCancelResult(self.job,'CANCEL_REQUESTED',True,2)
        self.client=TestClient(create_app(job_cancel_router=create_project_job_cancel_router(sessions=self.sessions,cancellations=self.cancel,origins=LoginOriginPolicy(['https://plm.example.test']))),base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.path=f'/api/v1/projects/{self.project}/jobs/{self.job}:cancel'
        self.headers={'origin':'https://plm.example.test','cookie':'plm_session='+(b'a'*32).hex(),'x-csrf-token':(b'b'*32).hex(),'idempotency-key':str(uuid4()),'if-match':'"v1"'}
    def post(self,**changes):return self.client.post(self.path,json={'reason':'Synthetic reason'},headers=self.headers|changes)
    def test_first_response_and_default_admin_closed(self):
        response=self.post();self.assertEqual(response.status_code,200)
        data=response.json()['data'];self.assertEqual(data['etag'],'"v2"');self.assertEqual(response.headers['etag'],data['etag'])
        self.assertEqual(set(data),{'job_id','state','changed','etag','status_url'})
        self.assertEqual(response.headers['cache-control'],'no-store');self.assertNotIn('reason',data)
        self.assertEqual(self.cancel.cancel.call_args.args[0].expected_version,1)
        with TestClient(create_app()) as closed:self.assertEqual(closed.post(self.path).status_code,404)
        self.assertEqual(self.client.post(f'/api/v1/admin/jobs/{self.job}:cancel',headers=self.headers,json={'reason':'x'}).status_code,404)
    def test_strict_conditions_before_cancel(self):
        headers=self.headers.copy();del headers['if-match']
        self.assertEqual(self.client.post(self.path,json={'reason':'x'},headers=headers).status_code,428)
        for key,value,status in (('if-match','W/"v1"',400),('if-match','*',400),('origin','https://evil.test',403),('cookie','plm_session=bad',401),('x-csrf-token','bad',403),('idempotency-key','short',422)):
            self.assertEqual(self.post(**{key:value}).status_code,status)
        self.cancel.cancel.assert_not_called()
    def test_strict_body_and_reason_validation(self):
        for body,status in (({},400),({'reason':'x','export_id':str(uuid4())},400),({'reason':True},422),({'reason':'bad\x00'},422),({'reason':''},422)):
            self.assertEqual(self.client.post(self.path,json=body,headers=self.headers).status_code,status)
        for body in (b'{"reason":"x","reason":"y"}',b'{"reason":NaN}',b'\xff',b'x'*8193):
            self.assertEqual(self.client.post(self.path,content=body,headers=self.headers|{'content-type':'application/json'}).status_code,400)
        self.cancel.cancel.assert_not_called()
    def test_public_errors_and_invalid_result_refuse(self):
        for code,status in (('CONFLICT_VERSION',409),('CONFLICT_IDEMPOTENCY',409),('RESOURCE_NOT_FOUND',404),('LICENSE_OPERATION_DENIED',403),('JOB_UNAVAILABLE',503)):
            self.cancel.cancel.side_effect=JobCancelError(code)
            response=self.post();self.assertEqual(response.status_code,status);self.assertEqual(set(response.json()),{'error','trace_id'})
        self.cancel.cancel.side_effect=RuntimeError('private SQL/path/key')
        response=self.post();self.assertEqual(response.status_code,503);self.assertNotIn('private',response.text)
        self.cancel.cancel.side_effect=None;self.cancel.cancel.return_value=JobCancelResult(uuid4(),'CANCELLED',True,2)
        self.assertEqual(self.post().status_code,503)
    def test_replay_never_skips_current_service(self):
        first=self.post();replay=self.post()
        self.assertEqual(first.json()['data'],replay.json()['data']);self.assertEqual(self.cancel.cancel.call_count,2)
        self.assertEqual(self.sessions.validate.call_count,2)
