"""Actual User HTTP with current real Session/Admin/License orchestration."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_detail import create_user_detail_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.user_read import AuthorizedUserReadService
from plm_assistant.modules.auth.infrastructure.user_read_repository import SqlAlchemyUserReadRepository

spec=spec_from_file_location('_user_http_internal',Path(__file__).resolve().parents[1]/'aut-04-a01-user-read'/'verify.py')
internal=module_from_spec(spec);spec.loader.exec_module(internal)

def exercise(v):
    internal.exercise(v)
    db=v['db'];tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    sessions=prod.SessionService(unit_of_work=v['uow'],repository=prod.SqlAlchemySessionRepository(),
        issue_access=prod.SqlAlchemyPasswordIssueAccess(prod.ScryptPasswordHasher()),audit=v['audit'],
        idempotency=prod.SqlAlchemyIdempotencyReceipts())
    reads=AuthorizedUserReadService(unit_of_work=v['uow'],access=prod.SqlAlchemyDeploymentReadAccess(),
        repository=SqlAlchemyUserReadRepository(),license_guard=v['guard'])
    app=create_app(user_detail_router=create_user_detail_router(sessions=sessions,reads=reads,
        origins=LoginOriginPolicy(['https://plm.example.test'])))
    path='/api/v1/admin/users/'+str(v['users'][0])
    headers={'cookie':'plm_session='+v['tokens'][1].hex()}
    with TestClient(app,base_url='https://plm.example.test') as client:
        def check(url=path,h=headers,status=200,code=None):
            before=snapshot();r=client.get(url,headers=h)
            assert r.status_code==status,(r.status_code,status,r.text)
            assert snapshot()==before
            if code:assert r.json()['error']['code']==code,r.text
            return r
        r=check();data=r.json()['data']
        assert set(data)=={'user_id','username_display','account_state','deployment_role','credential_version','created_at','updated_at','etag'}
        version,credential=db.execute('SELECT lock_version,credential_version FROM plm.auth_users WHERE user_id=%s',(v['users'][0],)).fetchone()
        assert data['etag']==r.headers['etag']==f'"v{version}"'
        check(h=headers|{'if-none-match':r.headers['etag']})
        check(h={'cookie':'plm_session='+v['tokens'][0].hex()},status=404,code='RESOURCE_NOT_FOUND')
        check(h={'cookie':'plm_session='+(b'?'*32).hex()},status=401,code='AUTH_SESSION_EXPIRED')
        check(h={'cookie':'plm_session='+(b'r'*32).hex()},status=401,code='AUTH_SESSION_EXPIRED')
        check('/api/v1/admin/users/'+str(uuid4()),status=404,code='RESOURCE_NOT_FOUND')
        check(path+'?extra=true',status=400,code='REQUEST_MALFORMED')
        check(h=headers|{'host':'evil.test'},status=403,code='AUTH_CSRF_INVALID')
        db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(v['users'][0],))
        try:assert check().json()['data']['account_state']=='DISABLED'
        finally:db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s",(v['users'][0],))
        name=db.execute('SELECT username_display FROM plm.auth_users WHERE user_id=%s',(v['users'][0],)).fetchone()[0]
        db.execute("UPDATE plm.auth_users SET username_display='Synthetic renamed metadata',lock_version=lock_version+1,updated_at=statement_timestamp() WHERE user_id=%s",(v['users'][0],))
        try:
            data=check().json()['data']
            assert data['etag']==f'"v{version+1}"' and data['credential_version']==credential
            assert data['username_display']=='Synthetic renamed metadata'
        finally:db.execute('UPDATE plm.auth_users SET username_display=%s,lock_version=lock_version+1,updated_at=statement_timestamp() WHERE user_id=%s',(name,v['users'][0]))
        db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
        try:check(h=headers|{'if-none-match':r.headers['etag']},status=404,code='RESOURCE_NOT_FOUND')
        finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
        v['guard'].enabled=False
        try:check(status=403,code='LICENSE_OPERATION_DENIED')
        finally:v['guard'].enabled=True
    with TestClient(create_app()) as default:assert default.get(path).status_code==404
    print('User HTTP PASS: actual current Session/Admin, disabled target visible, metadata ETag changes without credential version change, conditional GET cannot bypass revoked role; ordinary/unknown/revoked Session/target/Host/query/License refuse five tables unchanged, fixed public field set/default404. Positive License synthetic; Windows/list/writes/performance/Gate/package pending.')

if __name__=='__main__':internal.fixture.main(exercise=exercise)
