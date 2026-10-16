"""Actual Windows login/GET/renew/logout restricted projection, synthetic trust."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4, UUID
from unittest.mock import patch
from fastapi.testclient import TestClient
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView

spec=spec_from_file_location('_restricted_view_windows',Path(__file__).resolve().parents[1]/'aut-04-a11-p05-windows-user-state'/'verify.py')
w=module_from_spec(spec);spec.loader.exec_module(w)


def extra(v,settings):
    origin='https://plm.example.test';db=v['db']
    headers={'origin':origin,'cookie':'plm_session='+v['tokens'][1].hex(),
        'x-csrf-token':w.http.m.fixture.base.auth.CSRF.hex(),'idempotency-key':str(uuid4())}
    body={'username':'Synthetic Windows mandatory password','password':'Synthetic restricted password'}
    with TestClient(w.prod.create_production_platform_write_app(settings),base_url=origin,client=('127.0.0.1',51000)) as client:
        created=client.post('/api/v1/admin/users',headers=headers,json=body);assert created.status_code==201
        uid=UUID(created.json()['data']['user_id'])
        normal=client.post('/api/v1/auth/login',headers={'origin':origin},json=body)
        assert normal.status_code==200 and normal.json()['data']['password_change_required'] is False
        old_cookie=client.cookies.get('plm_session')
        # TEST_ONLY append pending reset credential, preserving original and no real reset claimed.
        with db.transaction():
            credential=db.execute('''INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,
                algorithm_id,parameter_set,must_change_password,changed_by)
                SELECT user_id,2,password_hash,algorithm_id,parameter_set,true,%s FROM plm.auth_password_credentials
                WHERE user_id=%s AND credential_version=1 RETURNING password_credential_id''',(v['users'][1],uid)).fetchone()[0]
            db.execute("UPDATE plm.auth_users SET active_password_credential_id=%s,credential_version=2,lock_version=lock_version+1,deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(credential,uid))
        assert client.get('/api/v1/auth/session',headers={'cookie':'plm_session='+old_cookie}).status_code==401
        restricted=client.post('/api/v1/auth/login',headers={'origin':origin},json=body)
        assert restricted.status_code==200,restricted.text
        data=restricted.json()['data'];assert data['password_change_required'] is True
        assert data['deployment_role']=='NONE' and data['authorized_projects']==[]
        assert data['user']['user_id']==str(uid)
        for word in ('password_hash','parameter_set','credential_id'):assert word not in restricted.text
        token=client.cookies.get('plm_session');csrf=data['csrf_token']
        got=client.get('/api/v1/auth/session');assert got.status_code==200,got.text
        assert got.json()['data']['password_change_required'] is True and got.json()['data']['authorized_projects']==[]
        denied=client.get('/api/v1/admin/users/'+str(uid));assert denied.status_code==404,denied.text
        class ForbiddenProjects:
            def for_user(self,*args):raise AssertionError('Restricted projection queried project membership')
        views=SqlAlchemySessionView(unit_of_work=v['uow'],projects=ForbiddenProjects())
        assert views.resolve_for_session(user_id=uid,session_token=bytes.fromhex(token)).public_data()['password_change_required'] is True
        for user,raw in ((uuid4(),bytes.fromhex(token)),(uid,b'?'*32),(uid,bytes.fromhex(old_cookie))):
            try:views.resolve_for_session(user_id=user,session_token=raw)
            except LookupError:pass
            else:raise AssertionError('Unbound or old Session projected')
        # Production exact source failure must not fall back to user-only resolve.
        with (patch.object(SqlAlchemySessionView,'resolve_for_session',side_effect=RuntimeError('private projection')),
            patch.object(SqlAlchemySessionView,'resolve',side_effect=AssertionError('Unsafe fallback'))):
            failed=client.get('/api/v1/auth/session');assert failed.status_code==503 and 'private' not in failed.text
        renewed=client.post('/api/v1/auth/session:renew',headers={'origin':origin,'x-csrf-token':csrf})
        assert renewed.status_code==200,renewed.text
        assert renewed.json()['data']['password_change_required'] is True
        assert renewed.json()['data']['deployment_role']=='NONE' and renewed.json()['data']['authorized_projects']==[]
        assert client.get('/api/v1/auth/session',headers={'cookie':'plm_session='+token}).status_code==401
        loggedout=client.post('/api/v1/auth/logout',headers={'origin':origin,
            'x-csrf-token':renewed.json()['data']['csrf_token'],'idempotency-key':str(uuid4())})
        assert loggedout.status_code==200 and 'Max-Age=0' in loggedout.headers['set-cookie'],loggedout.text
    print('PASS restricted Windows projection: real Scrypt login/current GET/renew emit strict required=true/NONE/no projects; project reader not called, bound wrong/old token refused, exact-source failure503 no fallback; business GET404, restricted logout works, ordinary false preserved. TEST_ONLY Credential2/role, synthetic trust; password-change/reset/UI/security/package pending.')


if __name__=='__main__':w.http.m.fixture.main(exercise=lambda v:w.exercise(v,extra=extra))
