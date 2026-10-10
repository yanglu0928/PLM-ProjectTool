"""Windows actual factory password HTTP, safe startup failures and unchanged closed modes."""
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
windows=load('_password_windows_trust','aut-04-a11-p05-windows-user-state')
http=load('_password_windows_http','aut-04-a12-p04-a03-password-change-http')


def extra(v,settings):
    http.exercise(v,make_app=lambda:prod.create_production_platform_write_app(settings))
    prefix='plm_assistant.entrypoints.production_login.'
    path='/api/v1/auth/password:change'
    origin='https://plm.example.test'
    username='Synthetic password HTTP target';password='Synthetic restricted HTTP final'
    with TestClient(prod.create_production_platform_write_app(settings),base_url=origin,client=('127.0.0.1',52000)) as client:
        assert client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,
            'password':'Synthetic HTTP third'}).status_code==401
        logged=client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,'password':password})
        assert logged.status_code==200 and logged.json()['data']['password_change_required'] is False,logged.text
        uid=logged.json()['data']['user']['user_id'];cookie=client.cookies.get('plm_session')
        csrf=logged.json()['data']['csrf_token'];newpassword='Synthetic Windows actual login password'
        changed=client.post(path,headers={'origin':origin,'x-csrf-token':csrf,'idempotency-key':str(uuid4())},
            json={'current_password':password,'new_password':newpassword})
        assert changed.status_code==200 and changed.json()['data']=={'credential_version':6},changed.text
        assert client.cookies.get('plm_session') is None
        assert client.get('/api/v1/auth/session',headers={'cookie':'plm_session='+cookie}).status_code==401
        assert client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,'password':password}).status_code==401
        newlogin=client.post('/api/v1/auth/login',headers={'origin':origin},json={'username':username,'password':newpassword})
        assert newlogin.status_code==200 and newlogin.json()['data']['user']['user_id']==uid,newlogin.text
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    for dep in ('SqlAlchemyPasswordChangeAccess','SqlAlchemyPasswordChangeRepository','SqlAlchemyPasswordChangeResults',
        'PasswordChangeReplayVerifier','PasswordChangeService','create_password_change_router'):
        before=snap()
        with patch(prefix+dep,side_effect=RuntimeError('Synthetic private dependency')) as fault:
            with TestClient(prod.create_production_platform_app(settings)) as client:
                assert client.post(path).status_code==404
            fault.assert_not_called()
            built=[];real=prod.create_database_runtime
            def tracked(url):
                runtime=real(url);runtime.dispose=Mock(wraps=runtime.dispose);built.append(runtime);return runtime
            with patch(prefix+'create_database_runtime',side_effect=tracked):
                try:prod.create_production_platform_write_app(settings)
                except prod.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                else:raise AssertionError('Half initialized password application returned')
            assert len(built)==1;built[0].dispose.assert_called_once();fault.assert_called_once()
        assert snap()==before
    for app in (create_app(),prod.create_production_login_app(settings)):
        with TestClient(app) as client:assert client.post(path).status_code==404
    print('PASS Windows password: actual write factory full P04A03 real PG/Scrypt HTTP matrix normal/restricted; actual login/change Cookie jar cleared/old Session401-old password401/new login200 sameUser; readonly/default/login404; six actual constructor faults dispose once/fixed errors/eight tables unchanged. Positive trust synthetic; old Windows state and absent formal trust regression also run. No formal service accounts/browser/performance/package proof.')


if __name__=='__main__':windows.http.m.fixture.main(exercise=lambda v:windows.exercise(v,extra=extra))
