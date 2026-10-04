"""Actual Session-CSRF/PG name PATCH + safe ETag and immutable create replay."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_name_patch import create_user_name_patch_router
from plm_assistant.modules.auth.api.user_create import create_user_create_router
from plm_assistant.modules.auth.api.user_detail import create_user_detail_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.user_name_patch import UserNamePatchService
from plm_assistant.modules.auth.application.user_read import AuthorizedUserReadService
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.application.managed_user_create import ManagedUserCreateService
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayVerifier
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.user_create_access import SqlAlchemyUserCreateAccess
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.user_name_patch_repository import SqlAlchemyUserNamePatchRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.user_read_repository import SqlAlchemyUserReadRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts

spec=spec_from_file_location('_name_patch_internal',Path(__file__).resolve().parents[1]
    /'aut-04-a10-p01-user-name-patch'/'verify.py')
internal=module_from_spec(spec);spec.loader.exec_module(internal)


def exercise(v, *, make_app=None, run_internal=True):
    if run_internal: internal.exercise(v)
    db=v['db']; hasher=ScryptPasswordHasher(); receipts=SqlAlchemyIdempotencyReceipts()
    results=SqlAlchemyUserCreateResultRepository(verifier=hasher)
    sessions=SessionService(unit_of_work=v['uow'],repository=SqlAlchemySessionRepository(),
        issue_access=SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    origins=LoginOriginPolicy(['https://plm.example.test'])
    create=ManagedUserCreateService(unit_of_work=v['uow'],access=SqlAlchemyUserCreateAccess(),
        license_guard=v['guard'],users=SqlAlchemyUserRepository(),results=results,
        replay_verifier=UserCreateReplayVerifier(source=results),hasher=hasher,audit=v['audit'],receipts=receipts)
    deps=dict(unit_of_work=v['uow'],access=SqlAlchemyUserCreateAccess(),repository=SqlAlchemyUserNamePatchRepository(),
        audit=v['audit'],license_guard=v['guard'])
    writes=UserNamePatchService(**deps)
    reads=AuthorizedUserReadService(unit_of_work=v['uow'],access=SqlAlchemyDeploymentReadAccess(),
        repository=SqlAlchemyUserReadRepository(),license_guard=v['guard'])
    app=create_app(user_create_router=create_user_create_router(sessions=sessions,writes=create,origins=origins),
        user_name_patch_router=create_user_name_patch_router(sessions=sessions,writes=writes,origins=origins),
        user_detail_router=create_user_detail_router(sessions=sessions,reads=reads,origins=origins))
    if make_app is not None: app=make_app()
    tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts','auth_user_create_results')
    def snap(): return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    base='/api/v1/admin/users'
    headers={'origin':'https://plm.example.test','cookie':'plm_session='+v['tokens'][1].hex(),
        'x-csrf-token':internal.fixture.base.auth.CSRF.hex(),'if-match':'"v1"'}
    body={'username':'Synthetic HTTP name original','password':'Synthetic HTTP name password'}
    create_headers=headers|{'idempotency-key':str(uuid4())}
    with TestClient(app,base_url='https://plm.example.test') as client:
        first=client.post(base,headers=create_headers,json=body); assert first.status_code==201,first.text
        first_data=first.json()['data']; path=first.headers['location']
        snapshot=snap()
        r=client.patch(path,headers=headers,json={'username':'  中文新名-e\u0301  '})
        assert r.status_code==200,r.text
        data=r.json()['data']; assert data['username_display']=='中文新名-é' and data['etag']==r.headers['etag']=='"v2"'
        assert data.keys()==first_data.keys()
        assert r.headers['cache-control']=='no-store' and r.headers['x-content-type-options']=='nosniff'
        assert 'set-cookie' not in r.headers and 'password' not in r.text and 'username_normalized' not in r.text
        after=snap()
        for table in ('auth_password_credentials','auth_sessions','plt_idempotency_receipts','auth_user_create_results'):
            assert after[table]==snapshot[table]
        def patch(h=headers,payload=None,status=200,code=None,url=path,raw=None):
            before=snap()
            r=client.patch(url,headers=h,json=payload or {'username':'中文新名-é'}) if raw is None else client.patch(url,headers=h,content=raw)
            assert r.status_code==status,(r.status_code,status,r.text)
            assert snap()==before
            if code: assert r.json()['error']['code']==code,r.text
            return r
        patch(status=409,code='CONFLICT_VERSION')
        noop=patch(h=headers|{'if-match':'"v2"'}); assert noop.json()['data']==data
        patch(h={k:v for k,v in headers.items() if k!='if-match'},status=428,code='CONFLICT_VERSION_REQUIRED')
        for name,value,status,code in (('if-match','W/"v2"',400,'REQUEST_MALFORMED'),
            ('origin','https://evil.test',403,'AUTH_CSRF_INVALID'),('host','evil.test',403,'AUTH_CSRF_INVALID'),
            ('cookie','plm_session='+(b'?'*32).hex(),401,'AUTH_SESSION_EXPIRED'),
            ('x-csrf-token',(b'?'*32).hex(),403,'AUTH_CSRF_INVALID'),
            ('cookie','plm_session='+v['tokens'][0].hex(),404,'RESOURCE_NOT_FOUND')):
            patch(h=headers|{name:value},status=status,code=code)
        patch(h=headers|{'if-match':'"v2"'},payload={'username':''},status=422,code='VALIDATION_FAILED')
        patch(payload={'username':'x','deployment_role':'DEPLOYMENT_ADMIN'},status=400,code='REQUEST_MALFORMED')
        patch(raw=b'{"username":"a","username":"b"}',h=headers|{'content-type':'application/json'},status=400,code='REQUEST_MALFORMED')
        patch(url=path+'?extra=true',status=400,code='REQUEST_MALFORMED')
        patch(url=base+'/'+str(uuid4()),status=404,code='RESOURCE_NOT_FOUND')
        duplicate=internal.fixture.base.auth.user(db,'Synthetic HTTP disabled reserved',b'q'*32,'NONE')
        db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(duplicate,))
        patch(h=headers|{'if-match':'"v2"'},payload={'username':'SYNTHETIC HTTP DISABLED RESERVED'},status=409,code='CONFLICT_DUPLICATE')
        v['guard'].enabled=False
        try: patch(h=headers|{'if-match':'"v2"'},status=403,code='LICENSE_OPERATION_DENIED')
        finally: v['guard'].enabled=True
        before=snap(); replay=client.post(base,headers=create_headers,json=body)
        assert replay.status_code==201 and replay.json()['data']==first_data and snap()==before
        before=snap(); current=client.get(path,headers={'cookie':headers['cookie']})
        assert current.status_code==200 and current.json()['data']==data and snap()==before
        db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(data['user_id'],))
        r=client.patch(path,headers=headers|{'if-match':'"v2"'},json={'username':'Synthetic HTTP disabled renamed'})
        assert r.status_code==200 and r.json()['data']['account_state']=='DISABLED' and r.headers['etag']=='"v3"'
    class FaultAudit:
        reached=False
        def append(self,tx,draft):
            v['audit'].append(tx,draft);self.reached=True
            raise RuntimeError('Synthetic post-Audit HTTP fault')
    fault=FaultAudit()
    broken=create_app(user_name_patch_router=create_user_name_patch_router(sessions=sessions,
        writes=UserNamePatchService(**(deps|{'audit':fault})),origins=origins))
    with TestClient(broken,base_url='https://plm.example.test') as client:
        before=snap();r=client.patch(path,headers=headers|{'if-match':'"v3"'},json={'username':'Must rollback'})
        assert r.status_code==503 and r.json()['error']['code']=='SYSTEM_UNAVAILABLE'
        assert fault.reached and snap()==before
    with TestClient(create_app()) as bare: assert bare.patch(path).status_code==404
    print('PASS User name HTTP: actual Session-CSRF/Admin/PG strict PATCH, safe200/ETag/no-store, '
        'fresh no-op/stale/disabled uniqueness and target state preserved, create-first replay/current GET; '
        'permission/browser/input/License refusals and actual post-Audit rollback six tables unchanged. '
        'Windows wiring/formal trust/performance/package remain pending.')


if __name__=='__main__': internal.fixture.main(exercise=exercise)
