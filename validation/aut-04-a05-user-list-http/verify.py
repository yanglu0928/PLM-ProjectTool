"""Actual User list HTTP full encrypted pagination and current role revocation."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_list import create_user_list_router
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.user_list import AuthorizedUserListService
from plm_assistant.modules.auth.infrastructure.user_read_repository import SqlAlchemyUserReadRepository

spec=spec_from_file_location('_user_list_http_actual',Path(__file__).resolve().parents[1]/'aut-04-a04-user-list'/'verify.py')
internal=module_from_spec(spec);spec.loader.exec_module(internal)

def exercise(v):
    internal.exercise(v)
    db=v['db'];tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    sessions=prod.SessionService(unit_of_work=v['uow'],repository=prod.SqlAlchemySessionRepository(),
        issue_access=prod.SqlAlchemyPasswordIssueAccess(prod.ScryptPasswordHasher()),audit=v['audit'],idempotency=prod.SqlAlchemyIdempotencyReceipts())
    reads=AuthorizedUserListService(unit_of_work=v['uow'],access=prod.SqlAlchemyDeploymentReadAccess(),
        repository=SqlAlchemyUserReadRepository(),license_guard=v['guard'])
    app=create_app(user_list_router=create_user_list_router(sessions=sessions,reads=reads,
        origins=LoginOriginPolicy(['https://plm.example.test']),cursors=UserListCursorCodec(b'u'*32)))
    headers={'cookie':'plm_session='+v['tokens'][1].hex()};path='/api/v1/admin/users'
    with TestClient(app,base_url='https://plm.example.test') as client:
        seen=[];cursors=set();cursor=None;first_cursor=None;before=snapshot()
        while True:
            params={'page_size':2}
            if cursor:params['cursor']=cursor
            r=client.get(path,params=params,headers=headers);assert r.status_code==200,r.text
            data=r.json()['data'];assert snapshot()==before
            assert r.headers['cache-control']=='no-store'
            seen.extend(item['user_id'] for item in data['items'])
            if not data['has_more']:
                assert data['next_cursor'] is None;break
            cursor=data['next_cursor'];assert cursor not in cursors;cursors.add(cursor)
            if first_cursor is None:first_cursor=cursor
            assert len(cursors)<20
        expected=[str(row[0]) for row in db.execute('SELECT user_id FROM plm.auth_users ORDER BY created_at DESC,user_id DESC')]
        assert seen==expected and len(seen)==len(set(seen))
        def reject(params,status,code,h=headers):
            before=snapshot();r=client.get(path,params=params,headers=h)
            assert r.status_code==status,(r.status_code,status,r.text)
            assert r.json()['error']['code']==code and snapshot()==before
        reject({'page_size':3,'cursor':first_cursor},400,'REQUEST_MALFORMED')
        reject({'page_size':2,'cursor':first_cursor+'='},400,'REQUEST_MALFORMED')
        reject({'page_size':2},404,'RESOURCE_NOT_FOUND',headers|{'cookie':'plm_session='+v['tokens'][0].hex()})
        for token in (b'?'*32,b'r'*32):reject({'page_size':2},401,'AUTH_SESSION_EXPIRED',headers|{'cookie':'plm_session='+token.hex()})
        reject({'page_size':2,'cursor':first_cursor},400,'REQUEST_MALFORMED',headers|{'cookie':'plm_session='+(bytes([31])*32).hex()})
        db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
        try:reject({'page_size':2,'cursor':first_cursor},404,'RESOURCE_NOT_FOUND')
        finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
        v['guard'].enabled=False
        try:reject({'page_size':2,'cursor':first_cursor},403,'LICENSE_OPERATION_DENIED')
        finally:v['guard'].enabled=True
    with TestClient(create_app()) as default:assert default.get(path).status_code==404
    print('User list HTTP PASS: actual encrypted complete pages/same timestamp UUID ties/no duplicates/disabled users and current Session/Admin; malformed/context/session/role/License refuse five tables unchanged, default404. Cursor key/License synthetic; Windows source/management writes/performance/three-platform/package/Gate pending.')

if __name__=='__main__':internal.internal.fixture.main(exercise=exercise)
