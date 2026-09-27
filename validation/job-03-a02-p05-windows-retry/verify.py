"""Actual Windows factories, safe retry metadata, actual HTTP retry->Worker."""
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec

ROOT=Path(__file__).resolve().parents[1]
def load(name,folder):
    spec=spec_from_file_location(name,ROOT/folder/'verify.py')
    module=module_from_spec(spec);spec.loader.exec_module(module);return module

http=load('_windows_retry_http','job-03-a02-p04-retry-http')
old=load('_windows_retry_list','job-01-a05-p05-windows')

def observe(v,service,command,first,key):
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('https://plm.example.test',))
    prefix='plm_assistant.entrypoints.production_login.'
    db=v['db']; index=0 if command.scope=='PROJECT' else 1
    path=f'/api/v1/projects/{command.project_id}/jobs/{command.job_id}' if index==0 else f'/api/v1/admin/jobs/{command.job_id}'
    headers={'cookie':'plm_session='+v['tokens'][index].hex()}
    tables=('job_jobs','job_attempts','job_leases','job_outbox_events','aud_events','aud_exports',
        'aud_export_acceptances','aud_export_retry_generations','plt_idempotency_receipts','aud_export_results')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    with ExitStack() as trust:
        trust.enter_context(patch(prefix+'read_database_url',return_value=v['url']))
        trust.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=SimpleNamespace(guard=v['guard'])))
        for name,codec in (
            ('create_windows_secret_list_cursor_codec',old.old.old.trust.SecretListCursorCodec(b'q'*32)),
            ('create_windows_project_member_cursor_codec',old.old.old.trust.MemberListCursorCodec(b'm'*32)),
            ('create_windows_project_department_cursor_codec',old.old.old.trust.DepartmentListCursorCodec(b'd'*32)),
            ('create_windows_document_list_cursor_codec',old.old.old.trust.DocumentListCursorCodec(b'l'*32)),
            ('create_windows_document_version_cursor_codec',old.old.old.trust.VersionListCursorCodec(b'v'*32)),
            ('create_windows_document_parse_cursor_codec',old.old.old.trust.ParseListCursorCodec(b'p'*32)),
            ('create_windows_audit_cursor_codec',old.old.old.trust.AuditListCursorCodec(b'a'*32)),
            ('create_windows_job_list_cursor_codec',JobListCursorCodec(b'j'*32))):
            trust.enter_context(patch(prefix+name,return_value=codec))
        trust.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service',return_value=object()))
        trust.enter_context(patch(prefix+'create_windows_document_upload_token_issuer',return_value=old.old.old.trust.HmacUploadTokenIssuer(
            provider=SimpleNamespace(resolve_key=lambda ref:b'u'*32),key_ref='document-upload-token-v1')))
        for factory,expected in ((prod.create_production_platform_app,False),(prod.create_production_platform_write_app,True)):
            with TestClient(factory(settings),base_url='https://plm.example.test') as client:
                before=snapshot();r=client.get(path,headers=headers)
                assert r.status_code==200,r.text
                assert r.json()['data']['retryable'] is expected,r.text
                # Complete pagination so metadata in details and list agrees.
                cursor=None;found=False
                while True:
                    params={'page_size':100}
                    if cursor:params['cursor']=cursor
                    r=client.get(path.rsplit('/',1)[0],headers=headers,params=params)
                    assert r.status_code==200,r.text
                    for item in r.json()['data']['items']:
                        if item['job_id']==str(command.job_id):
                            assert item['retryable'] is expected;found=True
                    if not r.json()['data']['has_more']:break
                    cursor=r.json()['data']['next_cursor']
                assert found and snapshot()==before
                if not expected:assert client.post(path+':retry',json={},headers=headers).status_code==405
                if expected and index==0:
                    db.execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER' WHERE project_id=%s AND user_id=%s",(command.project_id,v['users'][0]))
                    try:
                        r=client.get(path,headers=headers);assert r.status_code==200,r.text
                        assert r.json()['data']['retryable'] is False
                    finally:db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE project_id=%s AND user_id=%s",(command.project_id,v['users'][0]))
        for dependency in ('AuditUserRetrySourceReader','AuditUserRetryJobSources','SqlAlchemyAuditUserRetryJobSources',
            'SqlAlchemyAuditUserRetryFailureSources','AuditUserRetryService','JobRetryRequests','create_job_retry_router'):
            before=snapshot()
            with patch(prefix+dependency,side_effect=RuntimeError('private constructor failure')) as failed:
                try:prod.create_production_platform_write_app(settings)
                except prod.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                else:raise AssertionError('Partial retry app returned')
                failed.assert_called_once()
            assert snapshot()==before
        http.observe(v,service,command,first,key,make_app=lambda:prod.create_production_platform_write_app(settings))
    print('Windows retry PASS: real factories, write-only route, current PM/Admin FAILED metadata/detail-list agreement, readonly false/405, role downgrade false, seven constructor failures no partial app/no writes; original HTTP replay/newJob actual Worker success/refusals retained. Positive trust synthetic; formal deployment/Document retry/performance/Gate/package not proven.')

if __name__=='__main__':
    http.atomic.worker.fixture.main(exercise=lambda v:http.atomic.worker.exercise(v,observe_failed=lambda v,a,c:http.atomic.observe(v,a,c,observe_http=observe)))
