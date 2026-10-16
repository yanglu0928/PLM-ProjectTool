"""Actual PG current Admin and state/Session/Audit/first/receipt atomic behavior."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import hashlib
from psycopg import sql
from sqlalchemy import text
from plm_assistant.modules.auth.application.user_state import ChangeUserState,UserStateService,UserStateError
from plm_assistant.modules.auth.application.managed_user_create import ManagedUserCreateService,CreateManagedUser
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayVerifier
from plm_assistant.modules.auth.application.session_service import SessionService,PasswordIssueProof,SessionError
from plm_assistant.modules.auth.infrastructure.user_state_access import SqlAlchemyUserStateAccess
from plm_assistant.modules.auth.infrastructure.user_state_repository import SqlAlchemyUserStateRepository
from plm_assistant.modules.auth.infrastructure.user_state_result_repository import SqlAlchemyUserStateResultRepository
from plm_assistant.modules.auth.infrastructure.user_create_access import SqlAlchemyUserCreateAccess
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts

spec=spec_from_file_location('_state_atomic_publication',Path(__file__).resolve().parents[1]
    /'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];hasher=ScryptPasswordHasher();receipts=SqlAlchemyIdempotencyReceipts()
    firsts=SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=ManagedUserCreateService(unit_of_work=v['uow'],access=SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=SqlAlchemyUserRepository(),results=firsts,replay_verifier=UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    sessions=SessionService(unit_of_work=v['uow'],repository=SqlAlchemySessionRepository(),
        issue_access=SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    access=SqlAlchemyUserStateAccess();repo=SqlAlchemyUserStateRepository();results=SqlAlchemyUserStateResultRepository()
    deps=dict(unit_of_work=v['uow'],access=access,repository=repo,results=results,
        audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    service=UserStateService(**deps)
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results',
        'aud_events','plt_idempotency_receipts','auth_user_state_results')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def create(name):return creator.create(CreateManagedUser(v['tokens'][1],fixture.base.auth.CSRF,
        uuid4(),name,bytearray(b'Synthetic state password')),idempotency_key=str(uuid4()))
    def issue(user):return sessions.issue(user_id=user,trace_id=uuid4(),proof=PasswordIssueProof(bytearray(b'Synthetic state password')))
    def cmd(user,version,token=None,csrf=None):return ChangeUserState(v['tokens'][1] if token is None else token,
        fixture.base.auth.CSRF if csrf is None else csrf,uuid4(),user,version)
    def reject(command,key,code,owner=service,method='disable'):
        before=snap()
        try:getattr(owner,method)(command,idempotency_key=key)
        except UserStateError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('Unsafe User state accepted')
        assert snap()==before
    target=create('Synthetic atomic state target');uid=target.user_id
    active=issue(uid);already=issue(uid)
    assert sessions.revoke(token=already.token,csrf_token=already.csrf_token,trace_id=uuid4())
    old_revoked=db.execute('SELECT * FROM plm.auth_sessions WHERE session_id=%s',(already.session_id,)).fetchone()
    db.execute("""INSERT INTO plm.auth_sessions(user_id,credential_version,session_token_digest,csrf_digest,
        created_at,last_seen_at,idle_expires_at,absolute_expires_at) VALUES(%s,1,%s,%s,
        statement_timestamp()-interval '1 hour',statement_timestamp()-interval '1 hour',
        statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour')""",
        (uid,hashlib.sha256(b'e'*32).digest(),hashlib.sha256(b'c'*32).digest()))
    before=snap();key=str(uuid4());command=cmd(uid,1)
    with ThreadPoolExecutor(max_workers=2) as pool:disabled=list(pool.map(lambda _:service.disable(command,idempotency_key=key),range(2)))
    first=disabled[0];assert disabled[1]==first and first.first_view.account_state=='DISABLED'
    assert first.first_view.lock_version==2 and first.revoked_session_count==2
    assert db.execute('SELECT * FROM plm.auth_sessions WHERE session_id=%s',(already.session_id,)).fetchone()==old_revoked
    assert db.execute('SELECT count(*) FROM plm.auth_sessions WHERE user_id=%s AND revoked_at IS NULL',(uid,)).fetchone()==(0,)
    after=snap()
    for t in ('auth_password_credentials','auth_user_create_results'):assert after[t]==before[t]
    reject(cmd(uid,0),key,'CONFLICT_IDEMPOTENCY')
    reject(cmd(uid,1),str(uuid4()),'CONFLICT_VERSION')
    reject(cmd(uid,2),str(uuid4()),'CONFLICT_STATE')
    enablekey=str(uuid4());enablecmd=cmd(uid,2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        enables=list(pool.map(lambda _:service.enable(enablecmd,idempotency_key=enablekey),range(2)))
    enabled=enables[0];assert enables[1]==enabled
    assert enabled.first_view.account_state=='ENABLED' and enabled.first_view.lock_version==3 and enabled.revoked_session_count==0
    before=snap();assert service.disable(command,idempotency_key=key)==first;assert snap()==before
    try:sessions.validate(active.token)
    except SessionError:pass
    else:raise AssertionError('Disabled old Session revived on enable')
    fresh=issue(uid);assert sessions.validate(fresh.token).user_id==uid
    with v['uow']() as tx:assert results.get(tx,result_id=uuid4()) is None
    for token,csrf in ((v['tokens'][0],fixture.base.auth.CSRF),(b'?'*32,fixture.base.auth.CSRF),
        (v['tokens'][1],b'?'*32)):
        reject(cmd(uid,3,token,csrf),str(uuid4()),'AUTH_ACCESS_DENIED')
    reject(cmd(uuid4(),3),str(uuid4()),'RESOURCE_NOT_FOUND')
    db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
    try:reject(command,key,'AUTH_ACCESS_DENIED')
    finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
    v['guard'].enabled=False
    try:reject(cmd(uid,3),str(uuid4()),'LICENSE_OPERATION_DENIED')
    finally:v['guard'].enabled=True
    reached=set()
    class FaultRepo:
        def change(self,*args,**kw):
            result=repo.change(*args,**kw);reached.add('state-sessions');raise RuntimeError('Synthetic after actual state Sessions')
    class FaultAudit:
        def append(self,*args,**kw):
            v['audit'].append(*args,**kw);reached.add('audit');raise RuntimeError('Synthetic after actual Audit')
    class FaultResults:
        def record(self,*args,**kw):
            results.record(*args,**kw);reached.add('first');raise RuntimeError('Synthetic after actual first')
    class FaultReceipts:
        def __init__(self,step):self.step=step
        def reserve(self,*args,**kw):
            result=receipts.reserve(*args,**kw)
            if self.step=='reserve':reached.add('reserve');raise RuntimeError('Synthetic after actual reserve')
            return result
        def complete(self,*args,**kw):
            receipts.complete(*args,**kw);reached.add(self.step)
            if self.step=='complete':raise RuntimeError('Synthetic after actual complete')
            if self.step=='license':v['guard'].enabled=False
            if self.step=='revoke':args[0].session.execute(text("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),"
                "revoke_reason='ADMIN_REVOKED',lock_version=lock_version+1 WHERE user_id=:actor AND revoked_at IS NULL"),dict(actor=v['users'][1]))
    for override,code in (({'repository':FaultRepo()},'AUTH_STATE_UNAVAILABLE'),
        ({'audit':FaultAudit()},'AUTH_STATE_UNAVAILABLE'),({'results':FaultResults()},'AUTH_STATE_UNAVAILABLE')):
        reject(cmd(uid,3),str(uuid4()),code,UserStateService(**(deps|override)))
    for step,code in (('reserve','AUTH_STATE_UNAVAILABLE'),('complete','AUTH_STATE_UNAVAILABLE'),
        ('license','LICENSE_OPERATION_DENIED'),('revoke','AUTH_ACCESS_DENIED')):
        try:reject(cmd(uid,3),str(uuid4()),code,UserStateService(**(deps|{'receipts':FaultReceipts(step)})))
        finally:v['guard'].enabled=True
    assert reached=={'state-sessions','audit','first','reserve','complete','license','revoke'}
    commits=set()
    class CommitContext:
        def __init__(self,when):self.when=when;self.context=v['uow']()
        def __enter__(self):self.tx=self.context.__enter__();return self
        @property
        def session(self):return self.tx.session
        def commit(self):
            commits.add(self.when)
            if self.when=='after':self.tx.commit()
            raise RuntimeError('Synthetic commit confirmation boundary')
        def __exit__(self,*args):return self.context.__exit__(*args)
    reject(cmd(uid,3),str(uuid4()),'AUTH_STATE_UNAVAILABLE',
        UserStateService(**(deps|{'unit_of_work':lambda:CommitContext('before')})))
    lostkey=str(uuid4());lost=cmd(uid,3)
    try:UserStateService(**(deps|{'unit_of_work':lambda:CommitContext('after')})).disable(lost,idempotency_key=lostkey)
    except UserStateError as exc:assert exc.code=='AUTH_STATE_UNAVAILABLE'
    else:raise AssertionError('Lost commit confirmation guessed success')
    assert commits=={'before','after'}
    before=snap();recovered=service.disable(lost,idempotency_key=lostkey)
    assert recovered.first_view.lock_version==4 and snap()==before
    service.enable(cmd(uid,4),idempotency_key=str(uuid4()))
    # New password Session issuance and disable both take the target User lock.
    def issue_race():
        try:return issue(uid)
        except SessionError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        issuing=pool.submit(issue_race)
        stopped=pool.submit(service.disable,cmd(uid,5),idempotency_key=str(uuid4())).result(timeout=10)
        issued=issuing.result(timeout=10)
    assert stopped.first_view.lock_version==6
    assert db.execute('SELECT count(*) FROM plm.auth_sessions WHERE user_id=%s AND revoked_at IS NULL',(uid,)).fetchone()==(0,)
    if type(issued) is not str:
        try:sessions.validate(issued.token)
        except SessionError:pass
        else:raise AssertionError('Session issuance race bypassed disable')
    else:assert issued=='AUTH_ACCESS_DENIED',issued
    service.enable(cmd(uid,6),idempotency_key=str(uuid4()))
    zero=db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,created_by,updated_by) "
        "VALUES('Synthetic no credential state','synthetic no credential state',%s,%s) RETURNING user_id",
        (v['users'][1],v['users'][1])).fetchone()[0]
    reject(cmd(zero,0),str(uuid4()),'CONFLICT_STATE',method='enable')
    # Real lock timeout, not a simulated exception. No new state/receipt write.
    before=snap()
    class ObservedLock(SqlAlchemyUserStateAccess):
        failures=[]
        def lock_deployment(self,tx):
            try:return super().lock_deployment(tx)
            except Exception as exc:
                self.failures.append(getattr(getattr(exc,'orig',None),'sqlstate',None))
                raise
    observed_lock=ObservedLock()
    blocked_service=UserStateService(**(deps|{'access':observed_lock}))
    with v['uow']() as tx:
        assert access.lock_deployment(tx) is True
        with ThreadPoolExecutor(max_workers=1) as pool:
            def blocked():
                try:blocked_service.disable(cmd(uid,7),idempotency_key=str(uuid4()))
                except UserStateError as exc:return exc.code
                raise AssertionError('Held deployment lock ignored')
            assert pool.submit(blocked).result(timeout=8)=='AUTH_STATE_UNAVAILABLE'
    assert snap()==before
    assert observed_lock.failures==['55P03']
    def distinct_key(_):
        try:return service.disable(cmd(uid,7),idempotency_key=str(uuid4()))
        except UserStateError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:distinct=list(pool.map(distinct_key,range(2)))
    assert sum(type(x) is str and x=='CONFLICT_VERSION' for x in distinct)==1,distinct
    assert sum(type(x) is not str for x in distinct)==1
    # Fixture role assignment, NOT a production elevation command.
    admin=create('Synthetic real self state Admin')
    db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(admin.user_id,))
    own=issue(admin.user_id);selfcmd=cmd(admin.user_id,2,own.token,own.csrf_token)
    with v['uow']() as tx:
        original_proof=access.prove(tx,session_token=own.token,csrf_token=own.csrf_token,now=datetime.now(timezone.utc))
    class Clock:
        calls=0
        def __call__(self):
            self.calls+=1
            return datetime.now(timezone.utc)+(timedelta(hours=24) if self.calls==2 else timedelta())
    clock=Clock()
    reject(selfcmd,str(uuid4()),'AUTH_ACCESS_DENIED',UserStateService(**(deps|{'clock':clock})))
    assert clock.calls==2
    selfkey=str(uuid4())
    disabledself=service.disable(selfcmd,idempotency_key=selfkey)
    assert disabledself.actor_id==admin.user_id and disabledself.first_view.lock_version==3 and disabledself.revoked_session_count==1
    before=snap()
    with v['uow']() as tx:
        assert access.require_self_disabled(tx,proof=original_proof,command=selfcmd,
            result=disabledself,now=datetime.now(timezone.utc)) is True
        for forged_command,forged_proof in (
            (replace(selfcmd,csrf_token=b'?'*32),original_proof),
            (replace(selfcmd,session_token=b'?'*32),original_proof),
            (replace(selfcmd,trace_id=uuid4()),original_proof),
            (replace(selfcmd,expected_version=3),original_proof),
            (selfcmd,replace(original_proof,credential_id=uuid4())),
            (selfcmd,replace(original_proof,session_version=1)),
            (selfcmd,replace(original_proof,session_idle_expires_at=original_proof.session_idle_expires_at+timedelta(minutes=1)))):
            assert access.require_self_disabled(tx,proof=forged_proof,command=forged_command,
                result=disabledself,now=datetime.now(timezone.utc)) is False
    assert snap()==before
    reject(selfcmd,str(uuid4()),'AUTH_ACCESS_DENIED')
    service.enable(cmd(admin.user_id,3),idempotency_key=str(uuid4()))
    try:sessions.validate(own.token)
    except SessionError:pass
    else:raise AssertionError('Own disabled Session revived')
    own2=issue(admin.user_id)
    before=snap()
    assert service.disable(replace(selfcmd,session_token=own2.token,csrf_token=own2.csrf_token,
        trace_id=uuid4()),idempotency_key=selfkey)==disabledself
    assert snap()==before and sessions.validate(own2.token).user_id==admin.user_id
    db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
    try:reject(cmd(admin.user_id,4,own2.token,own2.csrf_token),str(uuid4()),'CONFLICT_STATE')
    finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
    # Two simultaneous self-disables cannot eliminate every enabled Admin.
    other=fixture.base.auth.user(db,'Synthetic competing state Admin',b'b'*32,'DEPLOYMENT_ADMIN')
    version=db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s',(other,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s",(v['users'][1],))
    try:
        commands=(cmd(admin.user_id,4,own2.token,own2.csrf_token),cmd(other,version,b'b'*32,fixture.base.auth.CSRF))
        def racing(command):
            try:return service.disable(command,idempotency_key=str(uuid4()))
            except UserStateError as exc:return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(racing,commands))
        assert sum(type(x) is str and x=='CONFLICT_STATE' for x in outcomes)==1,outcomes
        assert sum(type(x) is not str for x in outcomes)==1
        assert db.execute("SELECT count(*) FROM plm.auth_users WHERE state='ENABLED' AND deployment_role='DEPLOYMENT_ADMIN'").fetchone()==(1,)
    finally:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",(v['users'][1],))
    # Reciprocal Admin disables: loser is no longer a current Admin, cannot write.
    cross1=fixture.base.auth.user(db,'Synthetic reciprocal state A',b'x'*32,'DEPLOYMENT_ADMIN')
    cross2=fixture.base.auth.user(db,'Synthetic reciprocal state B',b'y'*32,'DEPLOYMENT_ADMIN')
    versions={u:db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s',(u,)).fetchone()[0] for u in (cross1,cross2)}
    commands=(cmd(cross2,versions[cross2],b'x'*32,fixture.base.auth.CSRF),
        cmd(cross1,versions[cross1],b'y'*32,fixture.base.auth.CSRF))
    def reciprocal(command):
        try:return service.disable(command,idempotency_key=str(uuid4()))
        except UserStateError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:cross=list(pool.map(reciprocal,commands))
    assert sum(type(x) is str and x=='AUTH_ACCESS_DENIED' for x in cross)==1,cross
    assert sum(type(x) is not str for x in cross)==1
    assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id IN (%s,%s) AND state='ENABLED'",
        (cross1,cross2)).fetchone()==(1,)
    print('PASS atomic state: actual current Admin-CSRF + PG/Scrypt target, sameKey concurrency/first replay after enable, '
        'all outstanding including expired revoked/old revoked untouched/no old Session revival; seven actual postwrite '
        'faults rollback seven tables, actual before/after commit fault and sameKey recovery no write. Real self-disable '
        'special proof, expiry final rollback, disabled actor cannot replay, lastAdmin and concurrent self-disables retain '
        'one enabled Admin; reciprocal disable loser denied, real deployment lock timeout no-write, password Session issuance '
        'race cannot leave active target Session, zero credential cannot enable. Fixture role promotions explicit; '
        'License synthetic; HTTP/Windows/performance/package pending.')


if __name__=='__main__':fixture.main(exercise=exercise)
