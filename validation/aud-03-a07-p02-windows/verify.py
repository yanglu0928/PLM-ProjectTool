"""Actual Windows write composition -> generic Worker -> safe result/download."""
from contextlib import ExitStack,contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import hashlib
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_submit_windows_fixture',ROOT/'validation/aud-03-a06-a04-p03-a06-p03-windows-composition/verify.py')
old=module_from_spec(spec);spec.loader.exec_module(old)

def exercise(v):
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('http://localhost',))
    prefix='plm_assistant.entrypoints.production_login.'
    database=create_worker_database_runtime(v['url']);original=database.unit_of_work
    @contextmanager
    def uow():
        with original() as tx:
            v['active'][0]+=1
            try:yield tx
            finally:v['active'][0]-=1
    database.unit_of_work=uow
    loop=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,
        license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],
        settings=AuditWorkerSettings('windows-submit-worker',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
    tables=('aud_exports','aud_export_acceptances','job_jobs','job_outbox_events','aud_events','plt_idempotency_receipts','job_leases','job_attempts','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    try:
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
                for app in (create_app(),production.create_production_login_app(settings),production.create_production_platform_app(settings)):
                    with TestClient(app,base_url='http://localhost') as client:
                        for path in ('/api/v1/admin/audit-exports',f'/api/v1/projects/{v["project"]}/audit-exports'):
                            assert client.post(path,json={}).status_code==404
                with TestClient(production.create_production_platform_write_app(settings),base_url='http://localhost') as client:
                    for scope in ('PROJECT','DEPLOYMENT'):
                        project=v['project'] if scope=='PROJECT' else None
                        path=f'/api/v1/projects/{project}/audit-exports' if project else '/api/v1/admin/audit-exports'
                        now=datetime.now(timezone.utc)
                        body=dict(purpose='PROJECT_GOVERNANCE' if project else 'SECURITY_REVIEW',start_at=(now-timedelta(hours=1)).isoformat(),end_at=now.isoformat())
                        headers={'origin':'http://localhost','cookie':'plm_session='+v['tokens'][0 if project else 1].hex(),
                            'x-csrf-token':old.fixture.base.auth.CSRF.hex(),'idempotency-key':str(uuid4())}
                        response=client.post(path,json=body,headers=headers);assert response.status_code==202,response.text
                        data=response.json()['data'];before=snapshot()
                        replay=client.post(path,json=body,headers=headers);assert replay.status_code==202 and replay.json()['data']==data and snapshot()==before
                        assert client.post(path,json=dict(body,action='OTHER'),headers=headers).status_code==409 and snapshot()==before
                        v['guard'].enabled=False
                        try:assert client.post(path,json=body,headers=headers).status_code==403 and snapshot()==before
                        finally:v['guard'].enabled=True
                        if project:
                            assert client.post(path,json=body,headers=dict(headers,cookie='plm_session='+v['tokens'][1].hex())).status_code==404 and snapshot()==before
                        status=client.get(data['status_url'],headers=headers);assert status.status_code==200 and status.json()['data']['state']=='PENDING'
                        assert loop.run(max_steps=1).executed==1
                        status=client.get(data['status_url'],headers=headers)
                        assert status.status_code==200 and status.json()['data']['state']=='SUCCEEDED' and status.headers['etag']=='"v2"'
                        result_path=f'/api/v1/projects/{project}/audit-exports/{data["export_id"]}' if project else f'/api/v1/admin/audit-exports/{data["export_id"]}'
                        meta=client.get(result_path,headers=headers);content=client.get(result_path+'/content',headers=headers)
                        assert meta.status_code==content.status_code==200
                        assert hashlib.sha256(content.content).hexdigest()==meta.json()['data']['file_sha256']
                        assert len(content.content)==meta.json()['data']['size_bytes']
                        before=snapshot();replay=client.post(path,json=body,headers=headers)
                        assert replay.status_code==202 and replay.json()['data']==data and snapshot()==before
                        assert v['db'].execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(data['job_id'],)).fetchone()==('SUCCEEDED',1)
                for name in ('AuditExportSubmitService','AuditExportSubmitAuthorization','create_audit_export_submit_router'):
                    before=snapshot()
                    with patch(prefix+name,side_effect=RuntimeError('private constructor detail')):
                        try:production.create_production_platform_write_app(settings)
                        except production.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                        else:raise AssertionError('partial write app returned')
                    assert snapshot()==before
            before=snapshot()
            try:production.create_production_platform_write_app(settings)
            except production.ProductionLoginStartupError:pass
            else:raise AssertionError('formal trust unexpectedly available')
            assert snapshot()==before
        loop.request_stop();assert loop.run().reason=='STOPPED'
    finally:
        with loop.quiescent():database.dispose()
    print('WINDOWS SUBMIT CHAIN INTERNAL PASS: real write factory/PG/Session-CSRF dualScope202->current Job GET->actual generic composed Worker->SUCCEEDEDv2->metadata/content actual SHA/size; idempotent/terminal replay no revival, conflict/License/admin-project refusal no writes; default/login/readonly POST404, new constructor and actual unavailable formal trust refuse startup. Positive credential/License/cursor/write sources test-injected; Worker in-process fixture, not process/service/browser/formal release proof.')

if __name__=='__main__':old.fixture.main(exercise=exercise)
