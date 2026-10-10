"""Actual Windows write factory name mutation and real old/new login behavior."""
from contextlib import ExitStack
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec

ROOT=Path(__file__).resolve().parents[1]
def load(name,folder):
    spec=spec_from_file_location(name,ROOT/folder/'verify.py')
    m=module_from_spec(spec);spec.loader.exec_module(m);return m
http=load('_windows_name_http','aut-04-a10-p02-user-name-http')
old=load('_windows_name_trust','aut-04-a09-p05-windows-user-create')


def exercise(v):
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('https://plm.example.test',))
    prefix='plm_assistant.entrypoints.production_login.'
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_login_rate_buckets',
        'aud_events','plt_idempotency_receipts','auth_user_create_results')
    def snap():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    library=old.old.old.old.old.trust
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
            headers={'origin':'https://plm.example.test','cookie':'plm_session='+v['tokens'][1].hex(),
                'x-csrf-token':http.internal.fixture.base.auth.CSRF.hex(),'idempotency-key':str(uuid4())}
            body={'username':'Synthetic Windows before rename','password':'Synthetic Windows name password'}
            with TestClient(prod.create_production_platform_write_app(settings),base_url='https://plm.example.test',
                client=('127.0.0.1',51000)) as client:
                first=client.post('/api/v1/admin/users',headers=headers,json=body);assert first.status_code==201,first.text
                path=first.headers['location'];uid=first.json()['data']['user_id']
                logged=client.post('/api/v1/auth/login',headers={'origin':headers['origin']},json=body)
                assert logged.status_code==200,logged.text
                current_cookie=client.cookies.get('plm_session')
                before=snap()
                denied=client.patch(path,headers={'origin':headers['origin'],'x-csrf-token':logged.json()['data']['csrf_token'],
                    'if-match':'"v1"'},json={'username':'Synthetic forbidden name'})
                assert denied.status_code==404 and snap()==before
                renamed=client.patch(path,headers=headers|{'if-match':'"v1"'},json={'username':'Synthetic Windows after rename'})
                assert renamed.status_code==200 and renamed.headers['etag']=='"v2"',renamed.text
                # Original target Session is still valid under stable UUID/password version.
                current=client.get('/api/v1/auth/session',headers={'cookie':'plm_session='+current_cookie})
                assert current.status_code==200 and current.json()['data']['user']['user_id']==uid,current.text
                wrong=client.post('/api/v1/auth/login',headers={'origin':headers['origin']},json=body)
                assert wrong.status_code==401,wrong.text
                new=client.post('/api/v1/auth/login',headers={'origin':headers['origin']},
                    json=body|{'username':'Synthetic Windows after rename'})
                assert new.status_code==200 and new.json()['data']['user']['user_id']==uid,new.text
                before=snap();replayed=client.post('/api/v1/admin/users',headers=headers,json=body)
                assert replayed.status_code==201 and replayed.json()['data']==first.json()['data'] and snap()==before
            for factory in (prod.create_production_platform_app,prod.create_production_platform_write_app):
                for dependency in ('SqlAlchemyUserNamePatchRepository','UserNamePatchService','create_user_name_patch_router'):
                    before=snap()
                    with patch(prefix+dependency,side_effect=RuntimeError('private name dependency')) as failed:
                        if factory is prod.create_production_platform_app:
                            with TestClient(factory(settings),base_url='https://plm.example.test') as client:
                                assert client.patch(path,headers=headers,json={'username':'Must refuse'}).status_code==405
                            failed.assert_not_called()
                        else:
                            try:factory(settings)
                            except prod.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                            else:raise AssertionError('Partial name-write runtime returned')
                            failed.assert_called_once()
                    assert snap()==before
            with TestClient(prod.create_production_login_app(settings)) as client:assert client.patch(path).status_code==404
        for factory in (prod.create_production_platform_app,prod.create_production_platform_write_app):
            before=snap()
            try:factory(settings)
            except prod.ProductionLoginStartupError:pass
            else:raise AssertionError('Actual missing trust accepted')
            assert snap()==before
    print('PASS Windows name PATCH: actual write factory full HTTP matrix, old login401/new login200 same UUID, '
        'preexisting target Session valid, NONE cannot rename, immutable create first replay seven tables no-write; '
        'readonly405/new dependencies not constructed, three actual constructor failures safe, login/default404, '
        'actual absent formal trust refuses. Positive trust synthetic; formal accounts/three-platform/performance/package pending.')


if __name__=='__main__':http.internal.fixture.main(exercise=exercise)
