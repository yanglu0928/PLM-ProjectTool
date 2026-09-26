"""Actual Windows write factory cancellation; positive trust explicitly synthetic."""
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor

spec=spec_from_file_location('_cancel_windows_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a06-p03-windows-composition'/'verify.py')
old=module_from_spec(spec);spec.loader.exec_module(old)

def exercise(v):
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('http://localhost',))
    prefix='plm_assistant.entrypoints.production_login.'
    tables=('aud_exports','aud_export_acceptances','job_jobs','job_outbox_events','aud_events','plt_idempotency_receipts','job_leases','job_attempts','aud_export_results','doc_file_objects','aud_export_cancel_versions')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def headers(version,token=None,key=None):return {'origin':'http://localhost','cookie':'plm_session='+(token or v['tokens'][0]).hex(),'x-csrf-token':old.fixture.base.auth.CSRF.hex(),'idempotency-key':key or str(uuid4()),'if-match':f'"v{version}"'}
    def reject(client,path,h,status):
        before=snapshot();response=client.post(path,json={'reason':'Synthetic Windows cancel'},headers=h)
        assert response.status_code==status,(response.status_code,status,response.text)
        assert snapshot()==before
    ack=AuditExportWorkerCancel(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=SqlAlchemyAuditExportCancelSources(),audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    with ExitStack() as stack:
        stack.enter_context(patch(prefix+'read_database_url',return_value=v['url']))
        with ExitStack() as trust:
            trust.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=SimpleNamespace(guard=v['guard'])))
            for name,codec in (
                ('create_windows_secret_list_cursor_codec',old.trust.SecretListCursorCodec(b'q'*32)),
                ('create_windows_project_member_cursor_codec',old.trust.MemberListCursorCodec(b'm'*32)),
                ('create_windows_project_department_cursor_codec',old.trust.DepartmentListCursorCodec(b'd'*32)),
                ('create_windows_document_list_cursor_codec',old.trust.DocumentListCursorCodec(b'l'*32)),
                ('create_windows_document_version_cursor_codec',old.trust.VersionListCursorCodec(b'v'*32)),
                ('create_windows_document_parse_cursor_codec',old.trust.ParseListCursorCodec(b'p'*32)),
                ('create_windows_audit_cursor_codec',old.trust.AuditListCursorCodec(b'a'*32)),
            ):trust.enter_context(patch(prefix+name,return_value=codec))
            trust.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service',return_value=object()))
            trust.enter_context(patch(prefix+'create_windows_document_upload_token_issuer',return_value=old.trust.HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda ref:b'u'*32),key_ref='document-upload-token-v1')))
            path=f'/api/v1/projects/{v["project"]}/jobs/{uuid4()}:cancel'
            for app,status in ((create_app(),404),(production.create_production_login_app(settings),404),(production.create_production_platform_app(settings),405)):
                with TestClient(app,base_url='http://localhost') as client:reject(client,path,headers(0),status)
            with TestClient(production.create_production_platform_write_app(settings),base_url='http://localhost') as client:
                now=datetime.now(timezone.utc)
                submit_body=dict(purpose='PROJECT_GOVERNANCE',start_at=(now-timedelta(hours=1)).isoformat(),end_at=now.isoformat())
                submitted=client.post(f'/api/v1/projects/{v["project"]}/audit-exports',json=submit_body,headers=headers(0))
                assert submitted.status_code==202,submitted.text
                data=submitted.json()['data'];path=data['status_url']+':cancel';h=headers(0)
                assert client.get(data['status_url'],headers=h).headers['etag']=='"v0"'
                missing=h.copy();del missing['if-match'];reject(client,path,missing,428)
                reject(client,path,h|{'if-match':'"v1"'},409)
                reject(client,path,headers(0,v['tokens'][1]),404)
                v['guard'].enabled=False
                try:reject(client,path,h,403)
                finally:v['guard'].enabled=True
                response=client.post(path,json={'reason':'Synthetic Windows cancel'},headers=h)
                assert response.status_code==200,response.text
                first=response.json()['data'];assert (first['state'],first['etag'])==('CANCELLED','"v2"')
                before=snapshot();replay=client.post(path,json={'reason':'Synthetic Windows cancel'},headers=h)
                assert replay.json()['data']==first and snapshot()==before
                assert client.get(first['status_url'],headers=h).json()['data']['state']=='CANCELLED'
                accepted,worker,_=v['prepare']('PROJECT',0)
                path=f'/api/v1/projects/{v["project"]}/jobs/{accepted.job_id}:cancel';h=headers(1)
                response=client.post(path,json={'reason':'Synthetic Windows cancel'},headers=h)
                assert response.status_code==200,response.text
                first=response.json()['data'];assert (first['state'],first['etag'])==('CANCEL_REQUESTED','"v2"')
                assert ack.acknowledge(worker).state=='CANCELLED'
                current=client.get(first['status_url'],headers=h)
                assert (current.json()['data']['state'],current.headers['etag'])==('CANCELLED','"v3"')
                before=snapshot();replay=client.post(path,json={'reason':'Synthetic Windows cancel'},headers=h)
                assert replay.json()['data']==first and replay.headers['etag']=='"v2"' and snapshot()==before
                reject(client,path,h|{'if-match':'"v3"'},409)
                reject(client,f'/api/v1/admin/jobs/{accepted.job_id}:cancel',h,405)
            for name in ('ProjectJobCancellation','AuditJobCancelOwner','AuditExportCancelRequestService','AuditExportCancelAuthorization','SqlAlchemyAuditExportCancelSources','create_project_job_cancel_router'):
                before=snapshot()
                with patch(prefix+name,side_effect=RuntimeError('private constructor details')):
                    try:production.create_production_platform_write_app(settings)
                    except production.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                    else:raise AssertionError('partial write app returned')
                assert snapshot()==before
        before=snapshot()
        try:production.create_production_platform_write_app(settings)
        except production.ProductionLoginStartupError:pass
        else:raise AssertionError('unavailable formal trust accepted')
        assert snapshot()==before
    print('JOB-02-A05 PASS: actual Windows write factory/PG/Session-CSRF submit PENDINGv0->HTTP cancel CANCELLEDv2 and real RUNNINGv1->requestv2->actual controlled Worker ack/current GETv3 vs first replayv2; missing/conflict/License/Admin-project no writes, default/login404/readonly405/admin405 no write; six new constructor faults and actual missing formal trust reject half startup eleven tables unchanged. Positive credential/trust test-injected, no formal account/service/browser/performance/Gate proof.')

if __name__=='__main__':old.fixture.main(exercise=exercise)
