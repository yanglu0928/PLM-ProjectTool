"""Actual Windows reset composition; positive trust remains explicitly synthetic."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from unittest.mock import patch,Mock
from uuid import uuid4
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.entrypoints.api import create_app

ROOT=Path(__file__).resolve().parents[1]
def load(name,folder):
    spec=spec_from_file_location(name,ROOT/folder/'verify.py');m=module_from_spec(spec);spec.loader.exec_module(m);return m
windows=load('_reset_windows_trust','aut-04-a11-p05-windows-user-state')
http=load('_reset_windows_http','aut-04-a12-p05-a06-reset-http')


def extra(v,settings):
    http.exercise(v,make_app=lambda:prod.create_production_platform_write_app(settings))
    origin='https://plm.example.test'
    admin={'origin':origin,'cookie':'plm_session='+v['tokens'][1].hex(),
        'x-csrf-token':http.m.fixture.base.auth.CSRF.hex(),'idempotency-key':str(uuid4())}
    username='Synthetic Windows reset login';old='Synthetic Windows reset old'
    temporary='Synthetic Windows reset temporary';normal='Synthetic Windows reset normal'
    with TestClient(prod.create_production_platform_write_app(settings),base_url=origin,client=('127.0.0.1',52000)) as client:
        created=client.post('/api/v1/admin/users',headers=admin,json={'username':username,'password':old})
        assert created.status_code==201,created.text
        uid=created.json()['data']['user_id'];resetpath=created.headers['location']+':reset-password'
        logged=client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,'password':old})
        assert logged.status_code==200,logged.text
        oldcookie=client.cookies.get('plm_session')
        resetheaders=admin|{'idempotency-key':str(uuid4()),'if-match':'"v1"'}
        body={'temporary_password':temporary,'must_change_password':True}
        first=client.post(resetpath,headers=resetheaders,json=body)
        assert first.status_code==200 and first.json()['data']=={'credential_version':2},first.text
        assert client.get('/api/v1/auth/session',headers={'cookie':'plm_session='+oldcookie}).status_code==401
        assert client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,'password':old}).status_code==401
        restricted=client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,'password':temporary})
        assert restricted.status_code==200 and restricted.json()['data']['password_change_required'] is True,restricted.text
        changed=client.post('/api/v1/auth/password:change',headers={'origin':origin,
            'x-csrf-token':restricted.json()['data']['csrf_token'],'idempotency-key':str(uuid4())},
            json={'current_password':temporary,'new_password':normal})
        assert changed.status_code==200 and client.cookies.get('plm_session') is None,changed.text
        logged=client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,'password':normal})
        assert logged.status_code==200 and logged.json()['data']['password_change_required'] is False,logged.text
        assert logged.json()['data']['user']['user_id']==uid
        replay=client.post(resetpath,headers=resetheaders,json=body)
        assert replay.status_code==200 and replay.json()['data']==first.json()['data'],replay.text
        assert replay.headers['etag']==first.headers['etag']
    prefix='plm_assistant.entrypoints.production_login.'
    path='/api/v1/admin/users/'+str(uuid4())+':reset-password'
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    for dep in ('SqlAlchemyPasswordResetAccess','SqlAlchemyPasswordResetRepository','SqlAlchemyPasswordResetResults',
        'PasswordResetReplayVerifier','PasswordResetService','create_password_reset_router'):
        before=snap()
        with patch(prefix+dep,side_effect=RuntimeError('Synthetic private reset dependency')) as fault:
            with TestClient(prod.create_production_platform_app(settings)) as client:
                assert client.post(path).status_code==405
            fault.assert_not_called()
            built=[];real=prod.create_database_runtime
            def tracked(url):
                runtime=real(url);runtime.dispose=Mock(wraps=runtime.dispose);built.append(runtime);return runtime
            with patch(prefix+'create_database_runtime',side_effect=tracked):
                try:prod.create_production_platform_write_app(settings)
                except prod.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                else:raise AssertionError('Half initialized reset application returned')
            assert len(built)==1;built[0].dispose.assert_called_once();fault.assert_called_once()
        assert snap()==before
    for app in (create_app(),prod.create_production_login_app(settings)):
        with TestClient(app) as client:assert client.post(path).status_code==404
    print('PASS Windows reset: actual write factory real PG/Scrypt A06 matrix; readonly405/default-login404; six reached constructor failures dispose once/fixed errors/nine tables unchanged. Positive trust synthetic; absent formal trust and old state regression also run. No browser/performance/production package proof.')


if __name__=='__main__':windows.http.m.fixture.main(exercise=lambda v:windows.exercise(v,extra=extra))
