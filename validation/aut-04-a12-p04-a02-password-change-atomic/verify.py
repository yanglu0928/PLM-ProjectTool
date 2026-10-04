"""Actual PG/Scrypt atomic service, rollback and fresh-auth historical recovery."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from psycopg import sql
from plm_assistant.modules.auth.application.password_change import ChangePassword,PasswordChangeService,PasswordChangeError
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeProof,PasswordChangeReplayVerifier
from plm_assistant.modules.auth.infrastructure.password_change_access import SqlAlchemyPasswordChangeAccess
from plm_assistant.modules.auth.infrastructure.password_change_repository import SqlAlchemyPasswordChangeRepository
from plm_assistant.modules.auth.infrastructure.password_change_result_repository import SqlAlchemyPasswordChangeResults

spec=spec_from_file_location('_password_atomic_fixture',Path(__file__).resolve().parents[1]/'aut-04-a11-p03-user-state-atomic'/'verify.py')
m=module_from_spec(spec);spec.loader.exec_module(m)


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    createfirst=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=createfirst,replay_verifier=m.UserCreateReplayVerifier(source=createfirst),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    results=SqlAlchemyPasswordChangeResults(verifier=hasher)
    deps=dict(unit_of_work=v['uow'],access=SqlAlchemyPasswordChangeAccess(verifier=hasher),
        repository=SqlAlchemyPasswordChangeRepository(),results=results,
        replay_verifier=PasswordChangeReplayVerifier(source=results),hasher=hasher,audit=v['audit'],receipts=receipts)
    service=PasswordChangeService(**deps)
    old=b'Synthetic atomic original';new='Synthetic 原子新密码'.encode();later=b'Synthetic atomic later'
    target=creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),
        'Synthetic atomic password change',bytearray(old)),idempotency_key=str(uuid4()))
    uid=target.user_id
    def issue(password):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password)))
    def cmd(session,before,after):return ChangePassword(session.token,session.csrf_token,uuid4(),
        PasswordChangeProof(bytearray(before),bytearray(after)))
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def run(owner,command,key,code=None):
        try:result=owner.change(command,idempotency_key=key)
        except PasswordChangeError as exc:
            assert code==exc.code,(code,exc.code);result=None
        else:assert code is None
        assert command.passwords.current_password==bytearray(len(command.passwords.current_password))
        assert command.passwords.new_password==bytearray(len(command.passwords.new_password))
        return result
    active=issue(old);other=issue(old)
    import hashlib
    db.execute('''INSERT INTO plm.auth_sessions(user_id,credential_version,session_token_digest,csrf_digest,
        created_at,last_seen_at,idle_expires_at,absolute_expires_at) VALUES(%s,1,%s,%s,
        statement_timestamp()-interval '1 hour',statement_timestamp()-interval '1 hour',
        statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour')''',
        (uid,hashlib.sha256(b'e'*32).digest(),hashlib.sha256(b'c'*32).digest()))
    before=snap()
    run(service,cmd(active,b'wrong',new),str(uuid4()),'AUTH_INVALID_CREDENTIALS');assert snap()==before
    bad=cmd(active,old,new)
    from dataclasses import replace
    run(service,replace(bad,csrf_token=b'?'*32),str(uuid4()),'AUTH_ACCESS_DENIED');assert snap()==before
    key=str(uuid4());first=run(service,cmd(active,old,new),key)
    assert first.credential_version==2 and first.revoked_session_count==3 and first.public_data()=={'credential_version':2}
    assert db.execute('SELECT count(*) FROM plm.auth_sessions WHERE user_id=%s AND revoked_at IS NULL',(uid,)).fetchone()[0]==0
    before=snap();run(service,cmd(active,old,new),key,'AUTH_ACCESS_DENIED');assert snap()==before
    fresh=issue(new)
    before=snap();assert run(service,cmd(fresh,old,new),key)==first;assert snap()==before
    for a,b in ((new,new),(old,new+b' '),(old,old)):
        run(service,cmd(fresh,a,b),key,'CONFLICT_IDEMPOTENCY');assert snap()==before
    second=run(service,cmd(fresh,new,later),str(uuid4()));assert second.credential_version==3
    current=issue(later);before=snap()
    assert run(service,cmd(current,old,new),key)==first;assert snap()==before
    # Each actual Port runs before injection; caller rollback includes receipt reserve and all preceding writes.
    class Fault:
        def __init__(self,real,method):self.real,self.method=real,method;self.hit=False
        def __getattr__(self,name):
            actual=getattr(self.real,name)
            if name!=self.method:return actual
            def call(*args,**kwargs):
                actual(*args,**kwargs);self.hit=True;raise RuntimeError('Synthetic postwrite fault')
            return call
    for dependency,method in (('repository','change'),('audit','append'),('results','record'),
        ('receipts','complete'),('access','require_changed')):
        fault=Fault(deps[dependency],method);owner=PasswordChangeService(**(deps|{dependency:fault}))
        before=snap();run(owner,cmd(current,later,b'Synthetic fault new'),str(uuid4()),'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
        assert fault.hit and snap()==before
    # Inject after individual real Credential/User/Session SQL and verify the entire transaction rolls back.
    from sqlalchemy import event
    for marker in ('INSERT INTO plm.auth_password_credentials','UPDATE plm.auth_users','UPDATE plm.auth_sessions'):
        reached=[]
        @contextmanager
        def sql_fault_uow():
            with v['uow']() as tx:
                connection=tx.session.connection()
                def after_sql(conn,cursor,statement,parameters,context,executemany):
                    if statement.startswith(marker):reached.append(True);raise RuntimeError('Synthetic SQL postwrite fault')
                event.listen(connection,'after_cursor_execute',after_sql)
                try:yield tx
                finally:event.remove(connection,'after_cursor_execute',after_sql)
        before=snap()
        run(PasswordChangeService(**(deps|{'unit_of_work':sql_fault_uow})),cmd(current,later,b'Synthetic SQL fault new'),
            str(uuid4()),'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
        assert reached==[True] and snap()==before
    rollback_reached=[]
    @contextmanager
    def rollback_commit_uow():
        with v['uow']() as tx:
            class Tx:
                session=tx.session
                def commit(self):rollback_reached.append(True);raise RuntimeError('Synthetic precommit fault')
            yield Tx()
    before=snap()
    run(PasswordChangeService(**(deps|{'unit_of_work':rollback_commit_uow})),cmd(current,later,b'Synthetic precommit new'),
        str(uuid4()),'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
    assert rollback_reached==[True] and snap()==before
    # Real commit followed by lost confirmation: no blind retry with revoked Session.
    committed=[]
    @contextmanager
    def lost_uow():
        with v['uow']() as tx:
            class Tx:
                session=tx.session
                def commit(self):tx.commit();committed.append(True);raise RuntimeError('Synthetic lost commit ack')
            yield Tx()
    lostkey=str(uuid4());recovered_password=b'Synthetic recovered password'
    run(PasswordChangeService(**(deps|{'unit_of_work':lost_uow})),cmd(current,later,recovered_password),lostkey,
        'AUTH_PASSWORD_CHANGE_UNAVAILABLE')
    assert committed==[True]
    recovered=issue(recovered_password);before=snap()
    recovered_first=run(service,cmd(recovered,later,recovered_password),lostkey)
    assert recovered_first.credential_version==4 and snap()==before
    # Two fresh concurrent requests with same original Session: exactly one commits, loser lacks new authority.
    racekey=str(uuid4());racepwd=b'Synthetic race password'
    def compete(_):
        command=cmd(recovered,recovered_password,racepwd)
        try:return service.change(command,idempotency_key=racekey)
        except PasswordChangeError as exc:return exc.code
        finally:assert not any(command.passwords.current_password) and not any(command.passwords.new_password)
    with ThreadPoolExecutor(max_workers=2) as pool:race=list(pool.map(compete,range(2)))
    assert sum(type(x) is str and x=='AUTH_ACCESS_DENIED' for x in race)==1
    assert sum(getattr(x,'credential_version',None)==5 for x in race)==1
    fresh=issue(racepwd);before=snap()
    assert run(service,cmd(fresh,recovered_password,racepwd),racekey).credential_version==5 and snap()==before
    # TEST_ONLY source creates restricted Credential6; conversion itself uses the actual production service.
    from sqlalchemy import select,insert,update
    from plm_assistant.modules.auth.infrastructure.user_orm import UserRow,PasswordCredentialRow
    from datetime import datetime,timezone
    with v['uow']() as tx:
        previous=tx.session.execute(select(PasswordCredentialRow).where(PasswordCredentialRow.user_id==uid,
            PasswordCredentialRow.credential_version==5)).scalar_one()
        restricted_id=tx.session.execute(insert(PasswordCredentialRow).values(user_id=uid,credential_version=6,
            password_hash=previous.password_hash,algorithm_id=previous.algorithm_id,parameter_set=previous.parameter_set,
            must_change_password=True,changed_by=uid).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        tx.session.execute(update(UserRow).where(UserRow.user_id==uid).values(active_password_credential_id=restricted_id,
            credential_version=6,lock_version=6));tx.commit()
    restricted=issue(racepwd)
    with v['uow']() as tx:
        proof=deps['access'].prove(tx,session_token=restricted.token,csrf_token=restricted.csrf_token,now=datetime.now(timezone.utc))
        assert proof.password_change_required is True and proof.user_view.deployment_role=='NONE'
    final_password=b'Synthetic unrestricted final'
    converted=run(service,cmd(restricted,racepwd,final_password),str(uuid4()))
    assert converted.credential_version==7
    normal=issue(final_password)
    with v['uow']() as tx:
        proof=deps['access'].prove(tx,session_token=normal.token,csrf_token=normal.csrf_token,now=datetime.now(timezone.utc))
        assert proof.password_change_required is False and proof.user_view.deployment_role=='NONE'
    keys=[str(uuid4()),str(uuid4())];candidates=[b'Synthetic different key A',b'Synthetic different key B']
    def different(index):
        command=cmd(normal,final_password,candidates[index])
        try:return service.change(command,idempotency_key=keys[index])
        except PasswordChangeError as exc:return exc.code
        finally:assert not any(command.passwords.current_password) and not any(command.passwords.new_password)
    with ThreadPoolExecutor(max_workers=2) as pool:different_results=list(pool.map(different,range(2)))
    assert sum(x=='AUTH_ACCESS_DENIED' for x in different_results)==1
    assert sum(getattr(x,'credential_version',None)==8 for x in different_results)==1
    winner=next(i for i,x in enumerate(different_results) if getattr(x,'credential_version',None)==8)
    newest=issue(candidates[winner]);before=snap()
    assert run(service,cmd(newest,final_password,candidates[winner]),keys[winner])==different_results[winner]
    assert snap()==before
    print('PASS actual PG/Scrypt atomic password change: current own proof; three old Sessions including expired revoked, new login, first/receipt historical dual-password replay with fresh auth; wrong password/CSRF/conflicts eight tables unchanged; five Port plus three individual SQL postwrite and precommit faults rollback; actual commit lost ack recovered after new login; same/differentKey concurrent single transition, revoked loser denied; TEST_ONLY restricted source converted by actual service and new normal login. No reset/HTTP/production/package proof.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
