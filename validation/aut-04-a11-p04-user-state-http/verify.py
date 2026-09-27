"""Actual isolated PG/ASGI state commands, safe first response and self Cookie."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.user_state import create_user_state_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError

spec=spec_from_file_location('_state_http_atomic',Path(__file__).resolve().parents[1]/'aut-04-a11-p03-user-state-atomic'/'verify.py')
m=module_from_spec(spec);spec.loader.exec_module(m)


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    firsts=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=firsts,replay_verifier=m.UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    deps=dict(unit_of_work=v['uow'],access=m.SqlAlchemyUserStateAccess(),repository=m.SqlAlchemyUserStateRepository(),
        results=m.SqlAlchemyUserStateResultRepository(),audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    service=m.UserStateService(**deps)
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','aud_events',
        'plt_idempotency_receipts','auth_user_state_results')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,
        uuid4(),name,bytearray(b'Synthetic HTTP state password')),idempotency_key=str(uuid4()))
    def issue(user):return sessions.issue(user_id=user,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(b'Synthetic HTTP state password')))
    def headers(token=None,csrf=None,version=1,key=None):return {'origin':'https://plm.example.test',
        'cookie':'plm_session='+(v['tokens'][1] if token is None else token).hex(),
        'x-csrf-token':(m.fixture.base.auth.CSRF if csrf is None else csrf).hex(),
        'if-match':f'"v{version}"','idempotency-key':key or str(uuid4())}
    def app(writes=service,session_port=sessions):return create_app(user_state_router=create_user_state_router(
        sessions=session_port,writes=writes,origins=LoginOriginPolicy(['https://plm.example.test'])))
    target=create('Synthetic state HTTP target');old=issue(target.user_id)
    path='/api/v1/admin/users/'+str(target.user_id);h=headers();key=h['idempotency-key']
    with TestClient(app(),base_url='https://plm.example.test') as client:
        r=client.post(path+':disable',headers=h);assert r.status_code==200,r.text
        first=r.json()['data'];assert first['account_state']=='DISABLED' and first['etag']=='"v2"'
        assert set(first)=={'user_id','username_display','account_state','deployment_role','credential_version','created_at','updated_at','etag'}
        assert 'set-cookie' not in r.headers and r.headers['etag']==first['etag']
        assert r.headers['cache-control']=='no-store' and r.headers['x-trace-id']==r.json()['trace_id']
        before=snap();replay=client.post(path+':disable',headers=h)
        assert replay.status_code==200 and replay.json()['data']==first and snap()==before
        assert client.post(path+':enable',headers=headers(version=2)).status_code==200
        before=snap();assert client.post(path+':disable',headers=h).json()['data']==first and snap()==before
        try:sessions.validate(old.token)
        except SessionError:pass
        else:raise AssertionError('Old target Session revived')
        fresh=issue(target.user_id);assert sessions.validate(fresh.token).user_id==target.user_id
        cases=[(headers(version=1),409,'CONFLICT_VERSION'),(headers(version=3,key=key),409,'CONFLICT_IDEMPOTENCY'),
            (headers(version=3,token=v['tokens'][0]),404,'RESOURCE_NOT_FOUND'),
            (headers(version=3,csrf=b'?'*32),403,'AUTH_CSRF_INVALID'),
            (headers(version=3)|{'origin':'https://evil.test'},403,'AUTH_CSRF_INVALID')]
        for bad,status,code in cases:
            before=snap();r=client.post(path+':disable',headers=bad)
            assert r.status_code==status and r.json()['error']['code']==code,(r.status_code,r.text)
            assert snap()==before
        for bad,status in (({'if-match':'W/"v3"'},400),({'idempotency-key':'short'},422)):
            before=snap();assert client.post(path+':disable',headers=headers(version=3)|bad).status_code==status;assert snap()==before
        before=snap();assert client.post(path+':disable',headers=headers(version=3),json={}).status_code==400;assert snap()==before
        v['guard'].enabled=False
        before=snap();assert client.post(path+':disable',headers=headers(version=3)).status_code==403;assert snap()==before
        v['guard'].enabled=True
        class FailAudit:
            def append(self,*args,**kwargs):
                v['audit'].append(*args,**kwargs)
                self.reached=True
                raise RuntimeError('Synthetic private after actual Audit')
        fault=FailAudit();fault.reached=False
        with TestClient(app(m.UserStateService(**(deps|{'audit':fault}))),base_url='https://plm.example.test') as broken:
            before=snap();r=broken.post(path+':disable',headers=headers(version=3))
            assert r.status_code==503 and fault.reached and snap()==before and 'private' not in r.text
        own=create('Synthetic HTTP self Admin')
        # Explicit TEST_ONLY role promotion, not a production role-management feature.
        db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(own.user_id,))
        own_session=issue(own.user_id);ownpath='/api/v1/admin/users/'+str(own.user_id)
        ownh=headers(own_session.token,own_session.csrf_token,2)
        r=client.post(ownpath+':disable',headers=ownh);assert r.status_code==200,r.text
        ownfirst=r.json()['data'];assert ownfirst['etag']=='"v3"'
        for attr in ('Max-Age=0','HttpOnly','Secure','SameSite=lax','Path=/'):assert attr in r.headers['set-cookie']
        before=snap();assert client.post(ownpath+':disable',headers=ownh).status_code==401;assert snap()==before
        assert client.post(ownpath+':enable',headers=headers(version=3)).status_code==200
        ownfresh=issue(own.user_id)
        before=snap();r=client.post(ownpath+':disable',headers=headers(ownfresh.token,ownfresh.csrf_token,2,ownh['idempotency-key']))
        assert r.status_code==200 and r.json()['data']==ownfirst and 'set-cookie' not in r.headers and snap()==before
        assert sessions.validate(ownfresh.token).user_id==own.user_id
        class PostReadFailure:
            reached=False
            def validate(self,token,**kwargs):
                if kwargs.get('require_csrf'):return sessions.validate(token,**kwargs)
                self.reached=True
                raise SessionError('SYSTEM_UNAVAILABLE')
        post=PostReadFailure();confirmh=headers(ownfresh.token,ownfresh.csrf_token,4)
        with TestClient(app(session_port=post),base_url='https://plm.example.test') as uncertain:
            r=uncertain.post(ownpath+':disable',headers=confirmh)
            assert r.status_code==503 and post.reached and 'set-cookie' not in r.headers
        assert db.execute('SELECT state,lock_version FROM plm.auth_users WHERE user_id=%s',(own.user_id,)).fetchone()==('DISABLED',5)
        assert db.execute('SELECT count(*) FROM plm.auth_user_state_results WHERE user_id=%s AND lock_version=5',(own.user_id,)).fetchone()==(1,)
        assert client.post(ownpath+':enable',headers=headers(version=5)).status_code==200
        final=issue(own.user_id);before=snap()
        r=client.post(ownpath+':disable',headers=headers(final.token,final.csrf_token,4,confirmh['idempotency-key']))
        assert r.status_code==200 and r.json()['data']['etag']=='"v5"' and 'set-cookie' not in r.headers and snap()==before
        assert sessions.validate(final.token).user_id==own.user_id
    print('PASS actual PG/ASGI state HTTP: safe both commands/first replay later enabled/current trace; current roles-CSRF-Origin-License-version-Key refusals seven tables unchanged; actual Audit-after-write rollback; self disable clears invalid Cookie, old401/new authenticated historical replay keeps fresh Session; actual postcommit Session-read failure503 with committed v5 first, re-enabled authenticated sameKey recovers without write or Cookie deletion. TEST_ONLY role promotion and synthetic License; Windows/performance/package pending.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
