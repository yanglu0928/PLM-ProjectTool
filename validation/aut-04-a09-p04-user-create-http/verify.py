"""Actual HTTP+PG current Session-CSRF/admin, safe first response/password binding."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import UUID, uuid4
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_create import create_user_create_router
from plm_assistant.modules.auth.api.user_detail import create_user_detail_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.managed_user_create import ManagedUserCreateService
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayVerifier
from plm_assistant.modules.auth.application.user_read import AuthorizedUserReadService
from plm_assistant.modules.auth.application.session_service import SessionService,PasswordIssueProof
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.user_create_access import SqlAlchemyUserCreateAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.infrastructure.user_read_repository import SqlAlchemyUserReadRepository
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts

spec=spec_from_file_location('_user_create_http_atomic',Path(__file__).resolve().parents[1]
    /'aut-04-a09-p03-user-create-atomic'/'verify.py')
internal=module_from_spec(spec);spec.loader.exec_module(internal)


def exercise(v,*,make_app=None,run_internal=True):
    if run_internal:internal.exercise(v)
    db=v['db'];hasher=ScryptPasswordHasher();results=SqlAlchemyUserCreateResultRepository(verifier=hasher)
    deps=dict(unit_of_work=v['uow'],access=SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=SqlAlchemyUserRepository(),results=results,replay_verifier=UserCreateReplayVerifier(source=results),
        hasher=hasher,audit=v['audit'],receipts=SqlAlchemyIdempotencyReceipts())
    writes=ManagedUserCreateService(**deps)
    sessions=SessionService(unit_of_work=v['uow'],repository=SqlAlchemySessionRepository(),
        issue_access=SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=SqlAlchemyIdempotencyReceipts())
    reads=AuthorizedUserReadService(unit_of_work=v['uow'],access=SqlAlchemyDeploymentReadAccess(),
        repository=SqlAlchemyUserReadRepository(),license_guard=v['guard'])
    origins=LoginOriginPolicy(['https://plm.example.test'])
    app=create_app(user_create_router=create_user_create_router(sessions=sessions,writes=writes,origins=origins),
        user_detail_router=create_user_detail_router(sessions=sessions,reads=reads,origins=origins))
    if make_app is not None:app=make_app()
    path='/api/v1/admin/users';body={'username':'Synthetic HTTP created user','password':'  合成HTTP原密码-é  '}
    headers={'origin':'https://plm.example.test','cookie':'plm_session='+v['tokens'][1].hex(),
        'x-csrf-token':internal.fixture.base.auth.CSRF.hex(),'idempotency-key':str(uuid4())}
    tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts','auth_user_create_results')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    with TestClient(app,base_url='https://plm.example.test') as client:
        first=client.post(path,headers=headers,json=body);assert first.status_code==201,(first.status_code,first.text)
        data=first.json()['data'];uid=data['user_id']
        assert set(data)=={'user_id','username_display','account_state','deployment_role','credential_version','created_at','updated_at','etag'}
        assert data['etag']==first.headers['etag']=='"v1"' and data['deployment_role']=='NONE'
        assert first.headers['location']==path+'/'+uid and first.headers['cache-control']=='no-store'
        assert first.headers['x-content-type-options']=='nosniff' and 'set-cookie' not in first.headers
        assert body['password'] not in first.text and 'password' not in first.text
        def post(h=headers,payload=body,status=201,code=None,url=path,raw=None):
            before=snapshot()
            r=client.post(url,headers=h,json=payload) if raw is None else client.post(url,headers=h,content=raw)
            assert r.status_code==status,(r.status_code,status,r.text)
            assert snapshot()==before
            if code:assert r.json()['error']['code']==code,r.text
            assert body['password'] not in r.text and 'password_hash' not in r.text
            return r
        replay=post();assert replay.json()['data']==data and replay.json()['trace_id']!=first.json()['trace_id']
        post(payload=body|{'password':'Different synthetic password'},status=409,code='CONFLICT_IDEMPOTENCY')
        post(payload=body|{'username':'Different synthetic name'},status=409,code='CONFLICT_IDEMPOTENCY')
        post(h=headers|{'idempotency-key':str(uuid4())},payload=body|{'username':body['username'].upper()},
            status=409,code='CONFLICT_DUPLICATE')
        proof=PasswordIssueProof(bytearray(body['password'].encode()))
        issued=sessions.issue(user_id=UUID(uid),trace_id=uuid4(),proof=proof)
        assert not any(proof.password) and sessions.validate(issued.token).user_id==issued.user_id
        post(h=headers|{'cookie':'plm_session='+issued.token.hex(),'x-csrf-token':issued.csrf_token.hex()},
            status=404,code='RESOURCE_NOT_FOUND')
        for h,status,code in ((headers|{'cookie':'plm_session='+(b'?'*32).hex()},401,'AUTH_SESSION_EXPIRED'),
            (headers|{'x-csrf-token':(b'?'*32).hex()},403,'AUTH_CSRF_INVALID'),
            (headers|{'origin':'https://evil.test'},403,'AUTH_CSRF_INVALID'),
            (headers|{'host':'evil.test'},403,'AUTH_CSRF_INVALID'),
            (headers|{'idempotency-key':'short'},422,'VALIDATION_FAILED')):
            post(h=h,status=status,code=code)
        post(url=path+'?extra=true',status=400,code='REQUEST_MALFORMED')
        for payload,status,code in ((body|{'deployment_role':'DEPLOYMENT_ADMIN'},400,'REQUEST_MALFORMED'),
            (body|{'password':''},422,'VALIDATION_FAILED'),(body|{'username':''},422,'VALIDATION_FAILED')):
            post(payload=payload,status=status,code=code)
        post(h=headers|{'content-type':'application/json'},raw=b'{"username":"x","password":"a","password":"b"}',
            status=400,code='REQUEST_MALFORMED')
        db.execute("UPDATE plm.auth_users SET state='DISABLED',username_display='Synthetic HTTP later renamed',"
            "lock_version=2,updated_at=statement_timestamp() WHERE user_id=%s",(uid,))
        replay=post();assert replay.json()['data']==data and replay.headers['etag']=='"v1"'
        before=snapshot();current=client.get(first.headers['location'],headers={'cookie':headers['cookie']})
        assert snapshot()==before
        assert current.status_code==200 and current.json()['data']['account_state']=='DISABLED'
        assert current.headers['etag']=='"v2"'
        post(h=headers|{'cookie':'plm_session='+issued.token.hex(),'x-csrf-token':issued.csrf_token.hex()},
            status=401,code='AUTH_SESSION_EXPIRED')
        db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
        try:post(status=404,code='RESOURCE_NOT_FOUND')
        finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
        v['guard'].enabled=False
        try:post(status=403,code='LICENSE_OPERATION_DENIED')
        finally:v['guard'].enabled=True
    class FailedAudit:
        reached=False
        def append(self,*args,**kw):
            v['audit'].append(*args,**kw);self.reached=True
            raise RuntimeError('Synthetic post-Audit HTTP failure')
    failed_audit=FailedAudit()
    broken=ManagedUserCreateService(**(deps|{'audit':failed_audit}))
    with TestClient(create_app(user_create_router=create_user_create_router(sessions=sessions,writes=broken,origins=origins)),
        base_url='https://plm.example.test') as client:
        before=snapshot();r=client.post(path,headers=headers|{'idempotency-key':str(uuid4())},
            json=body|{'username':'Synthetic HTTP Audit rollback'})
        assert r.status_code==503 and r.json()['error']['code']=='SYSTEM_UNAVAILABLE'
        assert failed_audit.reached,'Post-Audit rollback proof requires reaching the actual Audit write'
        assert snapshot()==before and body['password'] not in r.text
    with TestClient(create_app()) as bare:assert bare.post(path).status_code==404
    print('User create HTTP PASS: actual PG/Session-CSRF/Admin/Scrypt atomic safe201/Location/firstETag/no-store; '
        'same-key first replay and pwd-name-canonical conflict/strict body/browser/session/admin/License refusals '
        'six-table no-write, actual created credential issues valid Session (not loginHTTP), later target disabled/'
        'renamed GET v2 but original201 v1 replay unchanged, no revive. Actual post-Audit HTTP fault six-table rollback, '
        'default404. Positive License synthetic; Windows mounting/formal account/20-concurrent/performance/'
        'three-platform/complete management/Gate/package pending.')


if __name__=='__main__':internal.fixture.main(exercise=exercise)
