"""Actual two Windows factories, current User detail and startup fail-closed."""
from contextlib import ExitStack
from importlib.util import module_from_spec,spec_from_file_location
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
    m=module_from_spec(spec);spec.loader.exec_module(m);return m
http=load('_windows_user_http','aut-04-a02-user-detail-http')
old=load('_windows_user_trust','job-01-a05-p05-windows')

def exercise(v):
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('https://plm.example.test',))
    prefix='plm_assistant.entrypoints.production_login.'
    tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    with patch(prefix+'read_database_url',return_value=v['url']):
        with ExitStack() as trust:
            trust.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=SimpleNamespace(guard=v['guard'])))
            for name,codec in (
                ('create_windows_secret_list_cursor_codec',old.old.old.trust.SecretListCursorCodec(b'q'*32)),
                ('create_windows_project_member_cursor_codec',old.old.old.trust.MemberListCursorCodec(b'm'*32)),
                ('create_windows_project_department_cursor_codec',old.old.old.trust.DepartmentListCursorCodec(b'd'*32)),
                ('create_windows_document_list_cursor_codec',old.old.old.trust.DocumentListCursorCodec(b'l'*32)),
                ('create_windows_document_version_cursor_codec',old.old.old.trust.VersionListCursorCodec(b'v'*32)),
                ('create_windows_document_parse_cursor_codec',old.old.old.trust.ParseListCursorCodec(b'p'*32)),
                ('create_windows_audit_cursor_codec',old.old.old.trust.AuditListCursorCodec(b'a'*32)),
                ('create_windows_job_list_cursor_codec',JobListCursorCodec(b'j'*32))):trust.enter_context(patch(prefix+name,return_value=codec))
            trust.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service',return_value=object()))
            trust.enter_context(patch(prefix+'create_windows_document_upload_token_issuer',return_value=old.old.old.trust.HmacUploadTokenIssuer(
                provider=SimpleNamespace(resolve_key=lambda ref:b'u'*32),key_ref='document-upload-token-v1')))
            for i,factory in enumerate((prod.create_production_platform_app,prod.create_production_platform_write_app)):
                http.exercise(v,make_app=lambda:factory(settings),run_internal=i==0)
                for dependency in ('AuthorizedUserReadService','SqlAlchemyUserReadRepository','create_user_detail_router'):
                    before=snapshot()
                    with patch(prefix+dependency,side_effect=RuntimeError('private failure')) as failed:
                        try:factory(settings)
                        except prod.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                        else:raise AssertionError('Partial User app returned')
                        failed.assert_called_once()
                    assert snapshot()==before
            with TestClient(prod.create_production_login_app(settings),base_url='https://plm.example.test') as client:
                assert client.get('/api/v1/admin/users/'+str(v['users'][0])).status_code==404
        for factory in (prod.create_production_platform_app,prod.create_production_platform_write_app):
            before=snapshot()
            try:factory(settings)
            except prod.ProductionLoginStartupError:pass
            else:raise AssertionError('Formal trust unexpectedly supplied')
            assert snapshot()==before
    print('Windows User detail PASS: both actual factories/current real Session/Admin/ETag/target/License HTTP matrix and five-table no-write, three constructor faults each fail closed, default/login404 and actual absent formal trust refusal. Positive trust injected; no formal account/list/writes/performance/three-platform/package/Gate proof.')

if __name__=='__main__':http.internal.fixture.main(exercise=exercise)
