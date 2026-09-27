"""Actual PG/Scrypt atomic reset, current authorization and self recovery."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from dataclasses import replace
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from psycopg import sql
from sqlalchemy import event
from plm_assistant.modules.auth.application.password_reset import ResetPassword,PasswordResetService,PasswordResetError
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof,PasswordResetReplayVerifier
from plm_assistant.modules.auth.infrastructure.password_reset_access import SqlAlchemyPasswordResetAccess
from plm_assistant.modules.auth.infrastructure.password_reset_repository import SqlAlchemyPasswordResetRepository
from plm_assistant.modules.auth.infrastructure.password_reset_result_repository import SqlAlchemyPasswordResetResults
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

spec=spec_from_file_location('_reset_atomic_source',Path(__file__).resolve().parents[1]/'aut-04-a12-p05-a03-reset-password-source'/'verify.py')
s=module_from_spec(spec);spec.loader.exec_module(s);a=s.a;m=s.m


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    firsts=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=firsts,replay_verifier=m.UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    old=b'Synthetic atomic reset original';temporary='Synthetic 原子临时密码'.encode();normal=b'Synthetic atomic reset changed'
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),name,
        bytearray(old)),idempotency_key=str(uuid4()))
    def issue(user,password):return sessions.issue(user_id=user,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password)))
    def version(user):return db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s',(user,)).fetchone()[0]
    def cmd(user,expected,password=temporary,session=None):return ResetPassword(v['tokens'][1] if session is None else session.token,
        m.fixture.base.auth.CSRF if session is None else session.csrf_token,uuid4(),user,expected,True,PasswordResetProof(bytearray(password)))
    results=SqlAlchemyPasswordResetResults(verifier=hasher)
    deps=dict(unit_of_work=v['uow'],access=SqlAlchemyPasswordResetAccess(verifier=hasher),repository=SqlAlchemyPasswordResetRepository(),
        results=results,replay_verifier=PasswordResetReplayVerifier(source=results),hasher=hasher,audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    service=PasswordResetService(**deps)
    change_results=a.SqlAlchemyPasswordChangeResults(verifier=hasher)
    change=a.PasswordChangeService(unit_of_work=v['uow'],access=a.SqlAlchemyPasswordChangeAccess(verifier=hasher),
        repository=a.SqlAlchemyPasswordChangeRepository(),results=change_results,
        replay_verifier=a.PasswordChangeReplayVerifier(source=change_results),hasher=hasher,audit=v['audit'],receipts=receipts)
    def change_to_normal(user,before,after):
        active=issue(user,before)
        return change.change(a.ChangePassword(active.token,active.csrf_token,uuid4(),
            a.PasswordChangeProof(bytearray(before),bytearray(after))),idempotency_key=str(uuid4()))
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def run(owner,command,key,code=None):
        try:result=owner.reset(command,idempotency_key=key)
        except PasswordResetError as exc:assert exc.code==code,(code,exc.code);result=None
        else:assert code is None
        assert not any(command.password.temporary_password)
        return result
    target=create('Synthetic atomic reset target');uid=target.user_id;active=issue(uid,old);other=issue(uid,old)
    import hashlib
    db.execute('''INSERT INTO plm.auth_sessions(user_id,credential_version,session_token_digest,csrf_digest,
        created_at,last_seen_at,idle_expires_at,absolute_expires_at) VALUES(%s,1,%s,%s,
        statement_timestamp()-interval '1 hour',statement_timestamp()-interval '1 hour',
        statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour')''',
        (uid,hashlib.sha256(b'e'*32).digest(),hashlib.sha256(b'c'*32).digest()))
    before=snap()
    for command,code in ((cmd(uid,0),'CONFLICT_VERSION'),(replace(cmd(uid,1),must_change_password=False),'VALIDATION_FAILED'),
        (replace(cmd(uid,1),csrf_token=b'?'*32),'AUTH_ACCESS_DENIED'),(cmd(uid,1,session=active),'AUTH_ACCESS_DENIED'),
        (cmd(uuid4(),1),'RESOURCE_NOT_FOUND')):
        run(service,command,str(uuid4()),code);assert snap()==before
    v['guard'].enabled=False
    try:run(service,cmd(uid,1),str(uuid4()),'LICENSE_OPERATION_DENIED');assert snap()==before
    finally:v['guard'].enabled=True
    key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        firsts=list(pool.map(lambda _:run(service,cmd(uid,1),key),range(2)))
    first=firsts[0];assert firsts[0]==firsts[1] and first.credential_version==2 and first.revoked_session_count==3
    assert first.public_data()=={'credential_version':2}
    for session in (active,other):
        try:sessions.validate(session.token)
        except m.SessionError:pass
        else:raise AssertionError('Old target session survived reset')
    restricted=issue(uid,temporary)
    with v['uow']() as tx:
        from datetime import datetime,timezone
        assert deps['access'].prove(tx,session_token=restricted.token,csrf_token=restricted.csrf_token,now=datetime.now(timezone.utc)) is None
    before=snap();run(service,cmd(uid,1,temporary+b' '),key,'CONFLICT_IDEMPOTENCY');assert snap()==before
    run(service,cmd(uid,2),key,'CONFLICT_IDEMPOTENCY');assert snap()==before
    assert change_to_normal(uid,temporary,normal).credential_version==3
    fresh=issue(uid,normal);before=snap()
    assert run(service,cmd(uid,1),key)==first and snap()==before
    # Different keys with same target version: only one transition, the other conflicts rather than silently resets again.
    expected=version(uid);keys=[str(uuid4()),str(uuid4())];passwords=[b'Synthetic race reset A',b'Synthetic race reset B']
    def compete(index):
        command=cmd(uid,expected,passwords[index])
        try:return service.reset(command,idempotency_key=keys[index])
        except PasswordResetError as exc:return exc.code
        finally:assert not any(command.password.temporary_password)
    with ThreadPoolExecutor(max_workers=2) as pool:race=list(pool.map(compete,range(2)))
    assert sum(x=='CONFLICT_VERSION' for x in race)==1
    winner=next(i for i,x in enumerate(race) if getattr(x,'credential_version',None)==4)
    assert change_to_normal(uid,passwords[winner],normal).credential_version==5
    current=issue(uid,normal)
    class Fault:
        def __init__(self,real,method):self.real,self.method=real,method;self.hit=False
        def __getattr__(self,name):
            actual=getattr(self.real,name)
            if name!=self.method:return actual
            def call(*args,**kwargs):actual(*args,**kwargs);self.hit=True;raise RuntimeError('Synthetic postwrite reset fault')
            return call
    for dependency,method in (('repository','reset'),('audit','append'),('results','record'),('receipts','complete')):
        fault=Fault(deps[dependency],method);before=snap()
        run(PasswordResetService(**(deps|{dependency:fault})),cmd(uid,version(uid)),str(uuid4()),'AUTH_PASSWORD_RESET_UNAVAILABLE')
        assert fault.hit and snap()==before and sessions.validate(current.token).user_id==uid
    for marker in ('INSERT INTO plm.auth_password_credentials','UPDATE plm.auth_users','UPDATE plm.auth_sessions'):
        hit=[]
        @contextmanager
        def broken_uow():
            with v['uow']() as tx:
                connection=tx.session.connection()
                def after_sql(conn,cursor,statement,parameters,context,executemany):
                    if statement.startswith(marker):hit.append(True);raise RuntimeError('Synthetic SQL postwrite reset fault')
                event.listen(connection,'after_cursor_execute',after_sql)
                try:yield tx
                finally:event.remove(connection,'after_cursor_execute',after_sql)
        before=snap();run(PasswordResetService(**(deps|{'unit_of_work':broken_uow})),cmd(uid,version(uid)),str(uuid4()),'AUTH_PASSWORD_RESET_UNAVAILABLE')
        assert hit==[True] and snap()==before
    class FinalLicenseDenied:
        calls=0
        def require_valid(self,**kwargs):
            self.calls+=1
            if self.calls==2:raise RuntimeLicenseError('LICENSE_OPERATION_DENIED')
            v['guard'].require_valid(**kwargs)
    denied=FinalLicenseDenied();before=snap()
    run(PasswordResetService(**(deps|{'license_guard':denied})),cmd(uid,version(uid)),str(uuid4()),'LICENSE_OPERATION_DENIED')
    assert denied.calls==2 and snap()==before
    # Actual current role revoked inside this test UOW after all command writes; final proof must reject/rollback.
    from sqlalchemy import update,select,insert,func
    from plm_assistant.modules.auth.infrastructure.user_orm import UserRow,PasswordCredentialRow
    class RevokeActorAfterComplete:
        hit=False
        def __getattr__(self,name):return getattr(receipts,name)
        def complete(self,tx,**kwargs):
            receipts.complete(tx,**kwargs)
            tx.session.execute(update(UserRow).where(UserRow.user_id==v['users'][1]).values(
                deployment_role='NONE',lock_version=UserRow.lock_version+1))
            self.hit=True
    revoke=RevokeActorAfterComplete();before=snap()
    run(PasswordResetService(**(deps|{'receipts':revoke})),cmd(uid,version(uid)),str(uuid4()),'AUTH_ACCESS_DENIED')
    assert revoke.hit and snap()==before
    # Actual commit confirmation loss, recover via still-current other Admin rather than guessing failure.
    commits=[]
    @contextmanager
    def commit_fault(after):
        with v['uow']() as tx:
            class Tx:
                session=tx.session
                def commit(self):
                    commits.append(after)
                    if after:tx.commit()
                    raise RuntimeError('Synthetic reset commit acknowledgement')
            yield Tx()
    before=snap();run(PasswordResetService(**(deps|{'unit_of_work':lambda:commit_fault(False)})),cmd(uid,version(uid)),str(uuid4()),'AUTH_PASSWORD_RESET_UNAVAILABLE')
    assert commits==[False] and snap()==before
    lost_expected=version(uid);lost_key=str(uuid4())
    run(PasswordResetService(**(deps|{'unit_of_work':lambda:commit_fault(True)})),cmd(uid,lost_expected),lost_key,'AUTH_PASSWORD_RESET_UNAVAILABLE')
    assert commits==[False,True]
    before=snap();lost=run(service,cmd(uid,lost_expected),lost_key);assert lost.credential_version==6 and snap()==before
    disabled=create('Synthetic atomic reset disabled')
    states=m.UserStateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserStateAccess(),repository=m.SqlAlchemyUserStateRepository(),
        results=m.SqlAlchemyUserStateResultRepository(),audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    states.disable(m.ChangeUserState(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),disabled.user_id,1),idempotency_key=str(uuid4()))
    disabled_first=run(service,cmd(disabled.user_id,2),str(uuid4()))
    assert disabled_first.target_state=='DISABLED' and disabled_first.revoked_session_count==0
    assert db.execute('SELECT state FROM plm.auth_users WHERE user_id=%s',(disabled.user_id,)).fetchone()==('DISABLED',)
    try:issue(disabled.user_id,temporary)
    except m.SessionError:pass
    else:raise AssertionError('Disabled reset silently enabled login')
    # Explicit TEST_ONLY corrupt old profile: Admin reset repairs without needing user's broken old KDF.
    repair=create('Synthetic atomic reset profile repair')
    with v['uow']() as tx:
        previous=tx.session.execute(select(PasswordCredentialRow).where(PasswordCredentialRow.user_id==repair.user_id,
            PasswordCredentialRow.credential_version==1)).scalar_one()
        broken=tx.session.execute(insert(PasswordCredentialRow).values(user_id=repair.user_id,credential_version=2,
            password_hash=previous.password_hash,algorithm_id=previous.algorithm_id,parameter_set={'n':-1},
            must_change_password=False,changed_by=v['users'][1]).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        tx.session.execute(update(UserRow).where(UserRow.user_id==repair.user_id).values(active_password_credential_id=broken,
            credential_version=2,lock_version=2,updated_by=v['users'][1],updated_at=func.statement_timestamp()));tx.commit()
    repaired=run(service,cmd(repair.user_id,2),str(uuid4()))
    repaired_session=issue(repair.user_id,temporary)
    assert repaired.credential_version==3 and sessions.validate(repaired_session.token).credential_version==3
    # Last Admin self reset, lost commit ack, restricted login -> real change -> normal Admin historical recovery.
    own=create('Synthetic atomic reset sole Admin')
    db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(own.user_id,))
    own_session=issue(own.user_id,old);own_expected=version(own.user_id);own_key=str(uuid4())
    others=db.execute("SELECT user_id FROM plm.auth_users WHERE user_id<>%s AND state='ENABLED' AND deployment_role='DEPLOYMENT_ADMIN'",(own.user_id,)).fetchall()
    try:
        for row in others:db.execute("UPDATE plm.auth_users SET deployment_role='NONE',lock_version=lock_version+1 WHERE user_id=%s",row)
        assert db.execute("SELECT count(*) FROM plm.auth_users WHERE state='ENABLED' AND deployment_role='DEPLOYMENT_ADMIN'").fetchone()==(1,)
        # Precise self final false must rollback all preceding real writes.
        class BadSelfFinal:
            hit=False
            def __getattr__(self,name):return getattr(deps['access'],name)
            def require_self_reset(self,*args,**kwargs):
                assert deps['access'].require_self_reset(*args,**kwargs) is True;self.hit=True;return False
        badfinal=BadSelfFinal();before=snap()
        run(PasswordResetService(**(deps|{'access':badfinal})),cmd(own.user_id,own_expected,session=own_session),str(uuid4()),'AUTH_ACCESS_DENIED')
        assert badfinal.hit and snap()==before
        run(PasswordResetService(**(deps|{'unit_of_work':lambda:commit_fault(True)})),cmd(own.user_id,own_expected,session=own_session),own_key,'AUTH_PASSWORD_RESET_UNAVAILABLE')
        before=snap();run(service,cmd(own.user_id,own_expected,session=own_session),own_key,'AUTH_ACCESS_DENIED');assert snap()==before
        own_restricted=issue(own.user_id,temporary);before=snap()
        run(service,cmd(own.user_id,own_expected,session=own_restricted),own_key,'AUTH_ACCESS_DENIED');assert snap()==before
        v['guard'].enabled=False
        try:assert change_to_normal(own.user_id,temporary,normal).credential_version==3
        finally:v['guard'].enabled=True
        own_normal=issue(own.user_id,normal);before=snap()
        restored=run(service,cmd(own.user_id,own_expected,session=own_normal),own_key)
        assert restored.credential_version==2 and restored.actor_id==own.user_id and snap()==before
    finally:
        for row in others:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",row)
    print('PASS actual atomic reset PG/Scrypt: normal Admin/current-CSRF/License/expected/true flag, sameKey two threads one first and differentKey one version winner, three old Sessions incl expired revoked/restricted login/real change/history replay. Disabled remains disabled/count0; four Port and three SQL postwrite plus precommit/final License/actual role withdrawal nine tables rollback/current Session retained; actual commit loss recovered. TEST_ONLY broken old profile repaired with real reset/Scrypt login; soleAdmin role fixture self false final rollback/commit lost ack/old-restricted no new authority/real change even License-disabled then normal login recovers original reset first. License synthetic, no HTTP/production/performance/package proof.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
