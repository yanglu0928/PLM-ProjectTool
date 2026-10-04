"""Actual Windows write factory creates+logs in User; no production trust fallback."""
from contextlib import ExitStack
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec

ROOT=Path(__file__).resolve().parents[1]
def load(name,folder):
    spec=spec_from_file_location(name,ROOT/folder/'verify.py')
    m=module_from_spec(spec);spec.loader.exec_module(m);return m
http=load('_windows_user_create_http','aut-04-a09-p04-user-create-http')
old=load('_windows_user_create_trust','aut-04-a07-windows-user-list')


def exercise(v):
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('https://plm.example.test',))
    prefix='plm_assistant.entrypoints.production_login.'
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_login_rate_buckets',
        'aud_events','plt_idempotency_receipts','auth_user_create_results')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    library=old.old.old.old.trust
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
            body={'username':'Synthetic Windows login user','password':'Synthetic Windows login password'}
            with TestClient(prod.create_production_platform_write_app(settings),base_url='https://plm.example.test',
                client=('127.0.0.1',51000)) as client:
                created=client.post('/api/v1/admin/users',headers=headers,json=body)
                assert created.status_code==201,(created.status_code,created.text)
                data=created.json()['data'];uid=data['user_id']
                assert set(data)=={'user_id','username_display','account_state','deployment_role',
                    'credential_version','created_at','updated_at','etag'}
                assert data['username_display']==body['username'] and data['account_state']=='ENABLED'
                assert data['deployment_role']=='NONE' and data['credential_version']==1 and data['etag']=='"v1"'
                assert created.headers['ETag']=='"v1"' and created.headers['Location']=='/api/v1/admin/users/'+uid
                assert created.headers['Cache-Control']=='no-store' and created.headers.get('set-cookie') is None
                for field in ('created_at','updated_at'):
                    stamp=data[field]
                    assert stamp.endswith('Z') and datetime.fromisoformat(stamp.replace('Z','+00:00')).utcoffset()==timezone.utc.utcoffset(None)
                assert body['password'] not in created.text and 'password_hash' not in created.text
                logged=client.post('/api/v1/auth/login',headers={'origin':headers['origin']},json=body)
                assert logged.status_code==200,(logged.status_code,logged.text)
                assert logged.json()['data']['user']['user_id']==uid and logged.json()['data']['deployment_role']=='NONE'
                assert body['password'] not in logged.text and 'httponly' in logged.headers['set-cookie'].lower()
                current=client.get('/api/v1/auth/session')
                assert current.status_code==200 and current.json()['data']['user']['user_id']==uid
                # Actual newly issued nonAdmin Session cannot create users; original Admin replay still works.
                before=snapshot()
                denied=client.post('/api/v1/admin/users',headers={'origin':headers['origin'],
                    'x-csrf-token':logged.json()['data']['csrf_token'],'idempotency-key':str(uuid4())},
                    json={'username':'Synthetic forbidden new identity','password':'Synthetic forbidden password'})
                assert denied.status_code==404 and snapshot()==before
                before=snapshot();replayed=client.post('/api/v1/admin/users',headers=headers,json=body)
                assert replayed.status_code==201 and replayed.json()['data']==created.json()['data']
                assert replayed.headers['ETag']==created.headers['ETag'] and replayed.headers['Location']==created.headers['Location']
                assert snapshot()==before
            # GET route remains in read-only mode; POST must not mount there.
            before=snapshot()
            with TestClient(prod.create_production_platform_app(settings),base_url='https://plm.example.test') as client:
                assert client.post('/api/v1/admin/users',headers=headers,json=body).status_code==405
            assert snapshot()==before
            for factory in (prod.create_production_platform_app,prod.create_production_platform_write_app):
                for dependency in ('SqlAlchemyUserCreateResultRepository','UserCreateReplayVerifier',
                                   'ManagedUserCreateService','create_user_create_router'):
                    before=snapshot()
                    with patch(prefix+dependency,side_effect=RuntimeError('private User-create constructor')) as failed:
                        if factory is prod.create_production_platform_app:
                            with TestClient(factory(settings)):pass
                            failed.assert_not_called()
                        else:
                            try:factory(settings)
                            except prod.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                            else:raise AssertionError('Partial User-create write app returned')
                            failed.assert_called_once()
                    assert snapshot()==before
            with TestClient(prod.create_production_login_app(settings),base_url='https://plm.example.test') as client:
                assert client.post('/api/v1/admin/users',headers=headers,json=body).status_code==404
        # Positive trust exits: real factory must still refuse absent formal materials.
        for factory in (prod.create_production_platform_app,prod.create_production_platform_write_app):
            before=snapshot()
            try:factory(settings)
            except prod.ProductionLoginStartupError:pass
            else:raise AssertionError('Absent formal trust unexpectedly accepted')
            assert snapshot()==before
    print('Windows User create PASS: actual write factory current HTTP first/replay/conflict/history/permissions '
        'and real Scrypt; actual newly created user loginHTTP+HttpOnly Cookie/current Session works, role NONE '
        'cannot create users; seven-table replay/refusal no-write. Readonly405 and new constructors not called, '
        'four write constructor faults reached fail-closed; login/default404, actual absent formal trust refuses. '
        'Positive trust explicitly synthetic; formal target accounts/20-concurrent/performance/three-platform/'
        'full management/Gate/usable installer remain pending.')


if __name__=='__main__':http.internal.fixture.main(exercise=exercise)
