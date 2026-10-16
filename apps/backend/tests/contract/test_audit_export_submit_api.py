from dataclasses import replace
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.audit.api.submit_export import create_audit_export_submit_router
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent,AcceptedAuditExport,AuditExportSubmitError

class AuditExportSubmitApiTests(TestCase):
    def setUp(self):
        self.project=uuid4();self.sessions=Mock();self.exports=Mock()
        now=datetime.now(timezone.utc)
        self.body={'purpose':'PROJECT_GOVERNANCE','start_at':(now-timedelta(hours=1)).isoformat(),'end_at':now.isoformat()}
        spec=AuditExportSpec('PROJECT',self.project,self.body['purpose'],now-timedelta(hours=1),now)
        intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),now,spec,spec.fingerprint())
        self.accepted=AcceptedAuditExport(intent,uuid4(),uuid4(),uuid4(),now)
        self.exports.submit_idempotent.return_value=self.accepted
        self.client=TestClient(create_app(audit_export_submit_router=create_audit_export_submit_router(
            sessions=self.sessions,exports=self.exports,origins=LoginOriginPolicy(['https://plm.example.test']))),base_url='https://plm.example.test')
        self.addCleanup(self.client.close)
        self.path=f'/api/v1/projects/{self.project}/audit-exports'
        self.headers={'origin':'https://plm.example.test','cookie':'plm_session='+(b's'*32).hex(),
            'x-csrf-token':(b'c'*32).hex(),'idempotency-key':str(uuid4())}
    def post(self,body=None,**headers):return self.client.post(self.path,json=self.body if body is None else body,headers=dict(self.headers,**headers))
    def test_fixed_accepted_response_and_default_closed(self):
        with TestClient(create_app()) as default:self.assertEqual(default.post(self.path).status_code,404)
        response=self.post();self.assertEqual(response.status_code,202)
        data=response.json()['data'];self.assertEqual(set(data),{'job_id','export_id','state','status_url'})
        self.assertEqual(data['state'],'PENDING');self.assertEqual(data['job_id'],str(self.accepted.job_id))
        self.assertEqual(response.headers['location'],data['status_url']);self.assertEqual(response.headers['cache-control'],'no-store')
        call=self.exports.submit_idempotent.call_args
        self.assertEqual(call.args[0].spec,self.accepted.intent.spec)
        self.assertEqual(call.args[0].session_token,b's'*32)
        self.sessions.validate.assert_called_once_with(b's'*32,csrf_token=b'c'*32,require_csrf=True)
    def test_browser_headers_rejected_before_submit(self):
        for headers,status in (({'origin':'https://evil.test'},403),({'cookie':'plm_session=bad'},401),
            ({'x-csrf-token':'bad'},403),({'idempotency-key':''},422),({'host':'evil.test'},403)):
            self.assertEqual(self.post(**headers).status_code,status)
        self.exports.submit_idempotent.assert_not_called()
    def test_body_strictness_and_range(self):
        for body,status in ((dict(self.body,project_id=str(self.project)),400),([],400),
            (dict(self.body,purpose='ANY'),422),(dict(self.body,start_at='2026-09-01'),422),
            (dict(self.body,start_at='2026-01-01T00:00:00Z'),422),(dict(self.body,actor_id='0'*32),422)):
            self.assertEqual(self.post(body).status_code,status)
        for raw in ('{"purpose":"x","purpose":"y"}', '{"purpose":NaN}', 'x'*8193):
            self.assertEqual(self.client.post(self.path,content=raw,headers=dict(self.headers,**{'content-type':'application/json'})).status_code,400)
        self.exports.submit_idempotent.assert_not_called()
    def test_safe_service_and_session_errors(self):
        for code,status in (('CONFLICT_IDEMPOTENCY',409),('RESOURCE_NOT_FOUND',404),('LICENSE_OPERATION_DENIED',403),('AUDIT_UNAVAILABLE',503)):
            self.exports.submit_idempotent.side_effect=AuditExportSubmitError(code)
            self.assertEqual(self.post().status_code,status)
        self.exports.submit_idempotent.side_effect=RuntimeError('private path/SQL/Key')
        response=self.post();self.assertEqual(response.status_code,503);self.assertNotIn('private',response.text)
        self.sessions.validate.side_effect=SessionError('AUTH_ACCESS_DENIED')
        self.assertEqual(self.post().status_code,403)
    def test_mismatched_acceptance_not_returned(self):
        spec=replace(self.accepted.intent.spec,project_id=uuid4())
        intent=replace(self.accepted.intent,spec=spec,intent_hash=spec.fingerprint())
        self.exports.submit_idempotent.return_value=replace(self.accepted,intent=intent)
        self.assertEqual(self.post().status_code,503)
