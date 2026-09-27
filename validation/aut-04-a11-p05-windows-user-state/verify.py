"""Windows actual composition; positive trust explicitly synthetic."""
from contextlib import ExitStack
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
from uuid import uuid4
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec

ROOT=Path(__file__).resolve().parents[1]
def load(name,folder):
    spec=spec_from_file_location(name,ROOT/folder/'verify.py');m=module_from_spec(spec);spec.loader.exec_module(m);return m
http=load('_win_state_http','aut-04-a11-p04-user-state-http')
old=load('_win_state_old','aut-04-a10-p03-windows-user-name-patch')


def exercise(v):
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('https://plm.example.test',))
    prefix='plm_assistant.entrypoints.production_login.'
    library=old.old.old.old.old.old.trust
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_login_rate_buckets',
        'auth_user_create_results','auth_user_state_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    with patch(prefix+'read_database_url',return_value=v['url']):
        with ExitStack() as trust:
            trust.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=SimpleNamespace(guard=v['guard'])))
            for name,codec in (
                ('create_windows_secret_list_cursor_codec',library.SecretListCursorCodec(b'q'*32)),
                ('create_windows_project_member_cursor_codec',library.MemberListCursorCodec(b'm'*32)),
                ('create_windows_project_department_cursor_codec',library.DepartmentListCursorCodec(b'd'*32)),
                ('create_windows_document_list_cursor_codec',library.DocumentListCursorCodec(b'l'*32)),
                ('create_windows_document_version_cursor_codec',library.VersionListCursorCodec(b'v'*32)),
                ('create_windows_document_parse_cursor_codec',library.ParseListCursorCodec(b'p'*32)),
                ('create_windows_audit_cursor_codec',library.AuditListCursorCodec(b'a'*32)),
                ('create_windows_user_list_cursor_codec',UserListCursorCodec(b'u'*32)),
                ('create_windows_job_list_cursor_codec',JobListCursorCodec(b'j'*32))):
                trust.enter_context(patch(prefix+name,return_value=codec))
            trust.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service',return_value=object()))
            trust.enter_context(patch(prefix+'create_windows_document_upload_token_issuer',return_value=library.HmacUploadTokenIssuer(
                provider=SimpleNamespace(resolve_key=lambda ref:b'u'*32),key_ref='document-upload-token-v1')))
            http.exercise(v,make_app=lambda:prod.create_production_platform_write_app(settings))
            h={'origin':'https://plm.example.test','cookie':'plm_session='+v['tokens'][1].hex(),
                'x-csrf-token':http.m.fixture.base.auth.CSRF.hex(),'idempotency-key':str(uuid4())}
            body={'username':'Synthetic Windows state login','password':'Synthetic Windows state password'}
            with TestClient(prod.create_production_platform_write_app(settings),base_url='https://plm.example.test',client=('127.0.0.1',51000)) as client:
                created=client.post('/api/v1/admin/users',headers=h,json=body);assert created.status_code==201,created.text
                path=created.headers['location'];uid=created.json()['data']['user_id']
                logged=client.post('/api/v1/auth/login',headers={'origin':h['origin']},json=body);assert logged.status_code==200,logged.text
                cookie=client.cookies.get('plm_session');csrf=logged.json()['data']['csrf_token']
                before=snap()
                denied=client.post(path+':disable',headers={'origin':h['origin'],'cookie':'plm_session='+cookie,
                    'x-csrf-token':csrf,'idempotency-key':str(uuid4()),'if-match':'"v1"'})
                assert denied.status_code==404 and snap()==before
                stateh=h|{'if-match':'"v1"','idempotency-key':str(uuid4())}
                first=client.post(path+':disable',headers=stateh);assert first.status_code==200,first.text
                assert client.get('/api/v1/auth/session',headers={'cookie':'plm_session='+cookie}).status_code==401
                assert client.post('/api/v1/auth/login',headers={'origin':h['origin']},json=body).status_code==401
                enabled=client.post(path+':enable',headers=h|{'if-match':'"v2"','idempotency-key':str(uuid4())});assert enabled.status_code==200
                new=client.post('/api/v1/auth/login',headers={'origin':h['origin']},json=body)
                assert new.status_code==200 and new.json()['data']['user']['user_id']==uid,new.text
                assert client.get('/api/v1/auth/session',headers={'cookie':'plm_session='+cookie}).status_code==401
                before=snap();replay=client.post(path+':disable',headers=stateh)
                assert replay.status_code==200 and replay.json()['data']==first.json()['data'] and snap()==before
            for factory in (prod.create_production_platform_app,prod.create_production_platform_write_app):
                for dep in ('SqlAlchemyUserStateAccess','SqlAlchemyUserStateRepository','SqlAlchemyUserStateResultRepository','UserStateService','create_user_state_router'):
                    before=snap()
                    with patch(prefix+dep,side_effect=RuntimeError('private state dependency')) as fail:
                        if factory is prod.create_production_platform_app:
                            with TestClient(factory(settings),base_url='https://plm.example.test') as client:
                                for op in ('enable','disable'):assert client.post(path+':'+op,headers=h).status_code==405
                            fail.assert_not_called()
                        else:
                            built=[];real=prod.create_database_runtime
                            def tracked(url):
                                runtime=real(url);runtime.dispose=Mock(wraps=runtime.dispose);built.append(runtime);return runtime
                            with patch(prefix+'create_database_runtime',side_effect=tracked):
                                try:factory(settings)
                                except prod.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                                else:raise AssertionError('Partial state runtime returned')
                            assert len(built)==1
                            built[0].dispose.assert_called_once()
                            fail.assert_called_once()
                    assert snap()==before
            for app in (create_app(),prod.create_production_login_app(settings)):
                with TestClient(app) as client:assert client.post(path+':disable').status_code==404
        for factory in (prod.create_production_platform_app,prod.create_production_platform_write_app):
            before=snap()
            try:factory(settings)
            except prod.ProductionLoginStartupError:pass
            else:raise AssertionError('Absent formal trust accepted')
            assert snap()==before
    print('PASS Windows state: actual write factory P04 matrix/HTTP real create-Scrypt-login/NONE refusal/disable old401-disabled login401/enable new200 sameUUID-old still401/immutable first replay; readonly405/default-login404, five reached constructor failures safe and absent formal trust refuses. Positive trust synthetic; formal accounts/Server2025/performance/UI/package pending.')


if __name__=='__main__':http.m.fixture.main(exercise=exercise)
