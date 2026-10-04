"""Actual PG/Scrypt optional HTTP, malformed requests and current Cookie recovery."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.password_change import create_password_change_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy

spec=spec_from_file_location('_password_change_http',Path(__file__).resolve().parents[1]/'aut-04-a12-p04-a02-password-change-atomic'/'verify.py')
a=module_from_spec(spec);spec.loader.exec_module(a)
m=a.m


def exercise(v,make_app=None):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    firsts=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=firsts,replay_verifier=m.UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    old='Synthetic HTTP 原密码';new='Synthetic HTTP 新密码'
    target=creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),
        'Synthetic password HTTP target',bytearray(old.encode())),idempotency_key=str(uuid4()))
    uid=target.user_id
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    results=a.SqlAlchemyPasswordChangeResults(verifier=hasher)
    deps=dict(unit_of_work=v['uow'],access=a.SqlAlchemyPasswordChangeAccess(verifier=hasher),
        repository=a.SqlAlchemyPasswordChangeRepository(),results=results,replay_verifier=a.PasswordChangeReplayVerifier(source=results),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    service=a.PasswordChangeService(**deps)
    def issue(password):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password.encode())))
    def app(writes=service,session_port=sessions):
        if make_app is not None and writes is service and session_port is sessions:return make_app()
        return create_app(password_change_router=create_password_change_router(
            sessions=session_port,writes=writes,origins=LoginOriginPolicy(['https://plm.example.test'])))
    def headers(session,key=None):return {'origin':'https://plm.example.test','cookie':'plm_session='+session.token.hex(),
        'x-csrf-token':session.csrf_token.hex(),'idempotency-key':key or str(uuid4())}
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    path='/api/v1/auth/password:change';body={'current_password':old,'new_password':new}
    active=issue(old);key=str(uuid4())
    with TestClient(app(),base_url='https://plm.example.test') as client:
        before=snap()
        cases=[(headers(active)|{'origin':'https://evil.test'},body,403,'AUTH_CSRF_INVALID'),
            (headers(active)|{'x-csrf-token':('?'*32).encode().hex()},body,403,'AUTH_CSRF_INVALID'),
            (headers(active)|{'idempotency-key':'short'},body,422,'VALIDATION_FAILED'),
            (headers(active),body|{'current_password':'wrong'},401,'AUTH_INVALID_CREDENTIALS'),
            (headers(active),body|{'user_id':str(uid)},400,'REQUEST_MALFORMED'),
            (headers(active),body|{'new_password':None},400,'REQUEST_MALFORMED'),
            (headers(active),body|{'new_password':''},422,'VALIDATION_FAILED')]
        for h,payload,status,code in cases:
            r=client.post(path,headers=h,json=payload)
            assert r.status_code==status and r.json()['error']['code']==code,(status,r.status_code,r.text)
            assert snap()==before and 'set-cookie' not in r.headers
        for raw in ('{"current_password":"x","current_password":"y","new_password":"z"}',
            '{"current_password":NaN,"new_password":"x"}','x'*16385):
            r=client.post(path,headers=headers(active)|{'content-type':'application/json'},content=raw)
            assert r.status_code==400 and snap()==before
        assert client.post(path+'?user=x',headers=headers(active),json=body).status_code==400 and snap()==before
        assert client.post(path,headers=headers(active)|{'content-type':'text/plain'},content='{}').status_code==400 and snap()==before
        # Frozen password change has NO License requirement.
        v['guard'].enabled=False
        try:r=client.post(path,headers=headers(active,key),json=body)
        finally:v['guard'].enabled=True
        assert r.status_code==200,r.text
        assert r.json()['data']=={'credential_version':2}
        assert r.headers['cache-control']=='no-store' and r.headers['x-trace-id']==r.json()['trace_id']
        cookie=r.headers['set-cookie'].lower()
        assert 'max-age=0' in cookie and 'httponly' in cookie and 'secure' in cookie and 'samesite=lax' in cookie
        before=snap();assert client.post(path,headers=headers(active,key),json=body).status_code==401 and snap()==before
        fresh=issue(new);before=snap()
        r=client.post(path,headers=headers(fresh,key),json=body)
        assert r.status_code==200 and r.json()['data']=={'credential_version':2} and 'set-cookie' not in r.headers and snap()==before
        r=client.post(path,headers=headers(fresh,key),json=body|{'new_password':new+' '})
        assert r.status_code==409 and r.json()['error']['code']=='CONFLICT_IDEMPOTENCY' and snap()==before
    class AfterReadFault:
        reached=False
        def validate(self,*args,**kwargs):
            if not kwargs:self.reached=True;raise RuntimeError('Synthetic private postcommit read')
            return sessions.validate(*args,**kwargs)
    fault=AfterReadFault();recoverykey=str(uuid4());third='Synthetic HTTP third'
    with TestClient(app(session_port=fault),base_url='https://plm.example.test') as client:
        r=client.post(path,headers=headers(fresh,recoverykey),json={'current_password':new,'new_password':third})
        assert r.status_code==503 and fault.reached and 'private' not in r.text and 'set-cookie' not in r.headers
    current=issue(third);before=snap()
    with TestClient(app(),base_url='https://plm.example.test') as client:
        r=client.post(path,headers=headers(current,recoverykey),json={'current_password':new,'new_password':third})
        assert r.status_code==200 and r.json()['data']=={'credential_version':3} and 'set-cookie' not in r.headers and snap()==before
    with TestClient(create_app(),base_url='https://plm.example.test') as client:
        assert client.post(path,headers=headers(current),json=body).status_code==404
    from sqlalchemy import select,insert,update
    from plm_assistant.modules.auth.infrastructure.user_orm import UserRow,PasswordCredentialRow
    with v['uow']() as tx:
        previous=tx.session.execute(select(PasswordCredentialRow).where(PasswordCredentialRow.user_id==uid,
            PasswordCredentialRow.credential_version==3)).scalar_one()
        restricted_id=tx.session.execute(insert(PasswordCredentialRow).values(user_id=uid,credential_version=4,
            password_hash=previous.password_hash,algorithm_id=previous.algorithm_id,parameter_set=previous.parameter_set,
            must_change_password=True,changed_by=uid).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        tx.session.execute(update(UserRow).where(UserRow.user_id==uid).values(active_password_credential_id=restricted_id,
            credential_version=4,lock_version=4));tx.commit()
    restricted=issue(third);fourth='Synthetic restricted HTTP final'
    with TestClient(app(),base_url='https://plm.example.test') as client:
        r=client.post(path,headers=headers(restricted),json={'current_password':third,'new_password':fourth})
        assert r.status_code==200 and r.json()['data']=={'credential_version':5} and 'max-age=0' in r.headers['set-cookie'].lower()
    normal=issue(fourth)
    from datetime import datetime,timezone
    with v['uow']() as tx:
        assert deps['access'].prove(tx,session_token=normal.token,csrf_token=normal.csrf_token,
            now=datetime.now(timezone.utc)).password_change_required is False
    print('PASS actual optional password HTTP: strict origin/current Session-CSRF-Key and JSON; wrong inputs eight tables unchanged; no License gate; single version/trace/no-store, revoked Cookie cleared and old401; fresh-auth first replay keeps new Cookie/conflict409; actual postcommit read503 and new-login sameKey recovery; TEST_ONLY restricted source actual POST converts to normal login; default404. Windows/reset/browser UI/production/package unverified.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
