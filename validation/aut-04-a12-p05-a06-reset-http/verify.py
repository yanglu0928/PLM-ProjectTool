"""Actual PG/Scrypt reset HTTP, safe strong version and self Cookie recovery."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.password_reset import create_password_reset_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy

spec=spec_from_file_location('_reset_http_atomic',Path(__file__).resolve().parents[1]/'aut-04-a12-p05-a05-reset-atomic'/'verify.py')
r=module_from_spec(spec);spec.loader.exec_module(r);a=r.a;m=r.m


def exercise(v,make_app=None):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    firsts=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=firsts,replay_verifier=m.UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    old='Synthetic HTTP reset original';temporary='Synthetic HTTP 重置临时密码';normal='Synthetic HTTP reset normal'
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),name,
        bytearray(old.encode())),idempotency_key=str(uuid4()))
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    def issue(user,password):return sessions.issue(user_id=user,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password.encode())))
    results=r.SqlAlchemyPasswordResetResults(verifier=hasher)
    deps=dict(unit_of_work=v['uow'],access=r.SqlAlchemyPasswordResetAccess(verifier=hasher),repository=r.SqlAlchemyPasswordResetRepository(),
        results=results,replay_verifier=r.PasswordResetReplayVerifier(source=results),hasher=hasher,audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    service=r.PasswordResetService(**deps)
    change_results=a.SqlAlchemyPasswordChangeResults(verifier=hasher)
    changes=a.PasswordChangeService(unit_of_work=v['uow'],access=a.SqlAlchemyPasswordChangeAccess(verifier=hasher),
        repository=a.SqlAlchemyPasswordChangeRepository(),results=change_results,
        replay_verifier=a.PasswordChangeReplayVerifier(source=change_results),hasher=hasher,audit=v['audit'],receipts=receipts)
    def change(user,before,after):
        session=issue(user,before)
        return changes.change(a.ChangePassword(session.token,session.csrf_token,uuid4(),
            a.PasswordChangeProof(bytearray(before.encode()),bytearray(after.encode()))),idempotency_key=str(uuid4()))
    def app(writes=service,session_port=sessions):
        if make_app is not None and writes is service and session_port is sessions:return make_app()
        return create_app(password_reset_router=create_password_reset_router(sessions=session_port,writes=writes,
            origins=LoginOriginPolicy(['https://plm.example.test'])))
    def headers(expected=1,key=None,session=None):return {'origin':'https://plm.example.test',
        'cookie':'plm_session='+(v['tokens'][1] if session is None else session.token).hex(),
        'x-csrf-token':(m.fixture.base.auth.CSRF if session is None else session.csrf_token).hex(),
        'idempotency-key':key or str(uuid4()),'if-match':f'"v{expected}"'}
    def path(user):return '/api/v1/admin/users/'+str(user)+':reset-password'
    body={'temporary_password':temporary,'must_change_password':True}
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    target=create('Synthetic reset HTTP target');old_session=issue(target.user_id,old);key=str(uuid4())
    with TestClient(app(),base_url='https://plm.example.test') as client:
        before=snap()
        missing=headers();missing.pop('if-match')
        cases=[(missing,body,428,'CONFLICT_VERSION_REQUIRED'),(headers()|{'if-match':'W/"v1"'},body,400,'REQUEST_MALFORMED'),
            (headers(0),body,409,'CONFLICT_VERSION'),(headers()|{'origin':'https://evil.test'},body,403,'AUTH_CSRF_INVALID'),
            (headers()|{'x-csrf-token':('?'*32).encode().hex()},body,403,'AUTH_CSRF_INVALID'),
            (headers()|{'idempotency-key':'short'},body,422,'VALIDATION_FAILED'),
            (headers(session=old_session),body,404,'RESOURCE_NOT_FOUND'),
            (headers(),body|{'must_change_password':False},422,'VALIDATION_FAILED'),
            (headers(),body|{'must_change_password':1},422,'VALIDATION_FAILED'),
            (headers(),body|{'temporary_password':None},400,'REQUEST_MALFORMED'),
            (headers(),body|{'temporary_password':''},422,'VALIDATION_FAILED'),
            (headers(),body|{'user_id':str(target.user_id)},400,'REQUEST_MALFORMED')]
        for h,payload,status,code in cases:
            response=client.post(path(target.user_id),headers=h,json=payload)
            assert response.status_code==status and response.json()['error']['code']==code,(status,response.status_code,response.text)
            assert snap()==before and 'set-cookie' not in response.headers
        for raw in ('{"temporary_password":"x","temporary_password":"y","must_change_password":true}',
            '{"temporary_password":NaN,"must_change_password":true}','x'*16385):
            response=client.post(path(target.user_id),headers=headers()|{'content-type':'application/json'},content=raw)
            assert response.status_code==400 and snap()==before
        assert client.post(path(target.user_id)+'?x=1',headers=headers(),json=body).status_code==400 and snap()==before
        v['guard'].enabled=False
        try:assert client.post(path(target.user_id),headers=headers(),json=body).status_code==403 and snap()==before
        finally:v['guard'].enabled=True
        response=client.post(path(target.user_id),headers=headers(key=key),json=body)
        assert response.status_code==200 and response.json()['data']=={'credential_version':2},response.text
        assert response.headers['etag']=='"v2"' and response.headers['cache-control']=='no-store'
        assert response.headers['x-trace-id']==response.json()['trace_id'] and 'set-cookie' not in response.headers
        before=snap();replay=client.post(path(target.user_id),headers=headers(key=key),json=body)
        assert replay.status_code==200 and replay.json()['data']==response.json()['data'] and replay.headers['etag']=='"v2"' and snap()==before
        assert client.post(path(target.user_id),headers=headers(key=key),json=body|{'temporary_password':temporary+' '}).status_code==409 and snap()==before
        assert change(target.user_id,temporary,normal).credential_version==3
        before=snap();replay=client.post(path(target.user_id),headers=headers(key=key),json=body)
        assert replay.status_code==200 and replay.headers['etag']=='"v2"' and snap()==before
        class FailAudit:
            hit=False
            def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);self.hit=True;raise RuntimeError('Synthetic private Audit')
        fault=FailAudit()
        with TestClient(app(writes=r.PasswordResetService(**(deps|{'audit':fault}))),base_url='https://plm.example.test') as broken:
            before=snap();failed=broken.post(path(target.user_id),headers=headers(3),json=body)
            assert failed.status_code==503 and fault.hit and 'private' not in failed.text and snap()==before
        disabled=create('Synthetic reset HTTP disabled')
        states=m.UserStateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserStateAccess(),repository=m.SqlAlchemyUserStateRepository(),
            results=m.SqlAlchemyUserStateResultRepository(),audit=v['audit'],receipts=receipts,license_guard=v['guard'])
        states.disable(m.ChangeUserState(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),disabled.user_id,1),idempotency_key=str(uuid4()))
        response=client.post(path(disabled.user_id),headers=headers(2),json=body)
        assert response.status_code==200 and response.headers['etag']=='"v3"' and response.json()['data']=={'credential_version':2},response.text
        assert db.execute('SELECT state FROM plm.auth_users WHERE user_id=%s',(disabled.user_id,)).fetchone()==('DISABLED',)
        own=create('Synthetic reset HTTP own Admin')
        db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(own.user_id,))
        own_session=issue(own.user_id,old);ownkey=str(uuid4());ownh=headers(2,ownkey,own_session)
        response=client.post(path(own.user_id),headers=ownh,json=body)
        assert response.status_code==200 and response.headers['etag']=='"v3"' and response.json()['data']=={'credential_version':2},response.text
        cookie=response.headers['set-cookie'].lower()
        assert 'max-age=0' in cookie and 'httponly' in cookie and 'secure' in cookie and 'samesite=lax' in cookie
        before=snap();assert client.post(path(own.user_id),headers=ownh,json=body).status_code==401 and snap()==before
        restricted=issue(own.user_id,temporary);before=snap()
        assert client.post(path(own.user_id),headers=headers(2,ownkey,restricted),json=body).status_code==404 and snap()==before
        assert change(own.user_id,temporary,normal).credential_version==3
        current=issue(own.user_id,normal);before=snap()
        response=client.post(path(own.user_id),headers=headers(2,ownkey,current),json=body)
        assert response.status_code==200 and response.headers['etag']=='"v3"' and 'set-cookie' not in response.headers and snap()==before
    class AfterReadFault:
        hit=False
        def validate(self,*args,**kwargs):
            if not kwargs:self.hit=True;raise RuntimeError('Synthetic private postcommit read')
            return sessions.validate(*args,**kwargs)
    postread=AfterReadFault();recoverykey=str(uuid4());expected=db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s',(own.user_id,)).fetchone()[0]
    with TestClient(app(session_port=postread),base_url='https://plm.example.test') as client:
        response=client.post(path(own.user_id),headers=headers(expected,recoverykey,current),json=body)
        assert response.status_code==503 and postread.hit and 'private' not in response.text and 'set-cookie' not in response.headers
    assert change(own.user_id,temporary,normal).credential_version==5
    recovered=issue(own.user_id,normal);before=snap()
    with TestClient(app(),base_url='https://plm.example.test') as client:
        response=client.post(path(own.user_id),headers=headers(expected,recoverykey,recovered),json=body)
        assert response.status_code==200 and response.json()['data']=={'credential_version':4} and response.headers['etag']==f'"v{expected+1}"'
        assert 'set-cookie' not in response.headers and snap()==before
    with TestClient(create_app()) as client:assert client.post(path(target.user_id)).status_code==404
    print('PASS reset optional HTTP actual PG/Scrypt: strict source/Session-CSRF-Key/strong IfMatch missing428-bad400-stale409/body true and all rejection nine tables unchanged; normal/reset real change original replay ETag, disabled remains disabled and User ETag distinct from Credential version; actual Audit postwrite503 rollback; self200 secure Cookie deletion-old401-restricted404/real change-normalAdmin original replay keeps Cookie; postcommit read503 and real change/newlogin originalKey recovery; default404. License/role fixtures synthetic; Windows/browser/performance/package unverified.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
