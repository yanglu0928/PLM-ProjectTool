"""Both real Windows factories; explicit synthetic trust, actual PG/User/Job."""
from contextlib import ExitStack
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec as JobRegressionCursor
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_job_composition_fixture',ROOT/'validation/aud-03-a06-a04-p03-a06-p03-windows-composition/verify.py')
old=module_from_spec(spec);spec.loader.exec_module(old)

def exercise(v):
    jobs=[]
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,command,staged=v['prepare'](scope,3)
        path=f'/api/v1/projects/{v["project"]}/jobs/{accepted.job_id}' if scope=='PROJECT' else f'/api/v1/admin/jobs/{accepted.job_id}'
        jobs.append((accepted,command,staged,path,{'cookie':'plm_session='+v['tokens'][0 if scope=='PROJECT' else 1].hex()}))
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('http://localhost',))
    prefix='plm_assistant.entrypoints.production_login.'
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
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
                ('create_windows_job_list_cursor_codec', JobRegressionCursor(b'j' * 32)),
                ('create_windows_audit_cursor_codec',old.trust.AuditListCursorCodec(b'a'*32)),
            ):trust.enter_context(patch(prefix+name,return_value=codec))
            trust.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service',return_value=object()))
            trust.enter_context(patch(prefix+'create_windows_document_upload_token_issuer',return_value=old.trust.HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda ref:b'u'*32),key_ref='document-upload-token-v1')))
            for app in (create_app(),production.create_production_login_app(settings)):
                with TestClient(app,base_url='http://localhost') as client:
                    for *_,path,cookie in jobs:assert client.get(path,headers=cookie).status_code==404
            for index,factory in enumerate((production.create_production_platform_app,production.create_production_platform_write_app)):
                with TestClient(factory(settings),base_url='http://localhost') as client:
                    if index==0:
                        for accepted,command,staged,path,cookie in jobs:
                            before=snapshot();response=client.get(path,headers=cookie)
                            assert response.status_code==200 and snapshot()==before
                            assert response.json()['data']['state']=='RUNNING' and response.headers['etag']=='"v1"'
                            v['worker'].publish(command,staged)
                    for accepted,command,staged,path,cookie in jobs:
                        before=snapshot();response=client.get(path,headers=cookie)
                        assert response.status_code==200 and snapshot()==before
                        data=response.json()['data'];assert data['state']=='SUCCEEDED' and response.headers['etag']=='"v2"'
                        assert data['result_ref']=={'type':'AUDIT_EXPORT','id':str(command.export_id)}
                        assert client.get(path,headers={'cookie':'plm_session='+(b'X'*32).hex()}).status_code==401
                        v['guard'].enabled=False
                        try:assert client.get(path,headers=cookie).status_code==403
                        finally:v['guard'].enabled=True
                    accepted,command,staged,path,cookie=jobs[0]
                    assert client.get(path,headers=jobs[1][-1]).status_code==404
                    assert client.get(f'/api/v1/admin/jobs/{accepted.job_id}',headers=jobs[1][-1]).status_code==404
                for name in ('AuthorizedJobReadService','AuditJobReadProjection','SqlAlchemyJobReadRepository','create_job_detail_router'):
                    with patch(prefix+name,side_effect=RuntimeError('private constructor detail')):
                        try:factory(settings)
                        except production.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                        else:raise AssertionError('partial app returned')
        # Actual original License composition, no Guard fallback; formal materials unavailable.
        for factory in (production.create_production_platform_app,production.create_production_platform_write_app):
            before=snapshot()
            try:factory(settings)
            except production.ProductionLoginStartupError:pass
            else:raise AssertionError('formal trust unexpectedly available; evidence needs re-audit')
            assert snapshot()==before
    print('JOB WINDOWS INTERNAL PASS: both actual explicit factories/PG/current Session/Audit Owner GET; RUNNINGv1/SUCCEEDEDv2 and original result refs, no-write reads/401/License403/admin-project404; default/login404, four constructor failures per factory and actual unavailable formal trust refuse partial startup. DB credentials/positive License/cursors/write trust test-injected. Not formal key/account/SCM/other Owner/browser/package proof.')

if __name__=='__main__':old.fixture.main(exercise=exercise)
