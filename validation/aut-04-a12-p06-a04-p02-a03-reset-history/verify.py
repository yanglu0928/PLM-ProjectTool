"""Actual reset historical KDF outside UOW, current authority and bounded race."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.auth.application.password_reset import ResetPassword,PasswordResetService,PasswordResetError
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof

spec=spec_from_file_location('_history_atomic',Path(__file__).resolve().parents[1]/'aut-04-a12-p05-a05-reset-atomic'/'verify.py')
r=module_from_spec(spec);spec.loader.exec_module(r);m=r.m;a=r.a


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    creates=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=creates,replay_verifier=m.UserCreateReplayVerifier(source=creates),hasher=hasher,audit=v['audit'],receipts=receipts)
    old=b'Synthetic history original';temporary=b'Synthetic history temporary';normal=b'Synthetic history normal'
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),name,bytearray(old)),idempotency_key=str(uuid4()))
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    def issue(uid,password=old):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password)))
    results=r.SqlAlchemyPasswordResetResults(verifier=hasher)
    def service(firsts=results,hash_source=hasher):return PasswordResetService(unit_of_work=v['uow'],access=r.SqlAlchemyPasswordResetAccess(verifier=hasher),repository=r.SqlAlchemyPasswordResetRepository(),
        results=firsts,replay_verifier=r.PasswordResetReplayVerifier(source=firsts),hasher=hash_source,audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    actual=service()
    changes=a.SqlAlchemyPasswordChangeResults(verifier=hasher)
    change=a.PasswordChangeService(unit_of_work=v['uow'],access=a.SqlAlchemyPasswordChangeAccess(verifier=hasher),repository=a.SqlAlchemyPasswordChangeRepository(),
        results=changes,replay_verifier=a.PasswordChangeReplayVerifier(source=changes),hasher=hasher,audit=v['audit'],receipts=receipts)
    def cmd(session,uid,password=temporary):return ResetPassword(session.token,session.csrf_token,uuid4(),uid,1,True,PasswordResetProof(bytearray(password)))
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results','auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    class NoFreshHash:
        def hash_password(self,password):raise AssertionError('Fresh hash on historical replay')
    for i,kind in enumerate(('normal','role_withdraw','logout','renew','target_later_reset','license_withdraw')):
        caller=create(f'Synthetic history caller {i}');target=create(f'Synthetic history target {i}')
        # TEST_ONLY deployment role provisioning, actual authentication/commands thereafter.
        db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(caller.user_id,))
        session=issue(caller.user_id);key=str(uuid4());first=actual.reset(cmd(session,target.user_id),idempotency_key=key)
        restricted=issue(target.user_id,temporary)
        assert change.change(a.ChangePassword(restricted.token,restricted.csrf_token,uuid4(),a.PasswordChangeProof(bytearray(temporary),bytearray(normal))),idempotency_key=str(uuid4())).credential_version==3
        snapshots=[];checks=[]
        class HookVerifier:
            def verify_password(self,password,**kwargs):
                matched=hasher.verify_password(password,**kwargs)
                with db.transaction():
                    assert db.execute('SELECT pg_try_advisory_xact_lock(1347177793,1431524436)').fetchone()==(True,)
                    assert db.execute('SELECT user_id FROM plm.auth_users WHERE user_id=%s FOR UPDATE NOWAIT',(caller.user_id,)).fetchone()==(caller.user_id,)
                    assert db.execute('SELECT session_id FROM plm.auth_sessions WHERE session_id=%s FOR UPDATE NOWAIT',(session.session_id,)).fetchone()==(session.session_id,)
                checks.append(True)
                if kind=='role_withdraw':db.execute("UPDATE plm.auth_users SET deployment_role='NONE',lock_version=lock_version+1 WHERE user_id=%s",(caller.user_id,))
                elif kind=='logout':sessions.logout(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4(),idempotency_key=str(uuid4()))
                elif kind=='renew':sessions.renew(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4())
                elif kind=='target_later_reset':
                    again=ResetPassword(session.token,session.csrf_token,uuid4(),target.user_id,3,True,PasswordResetProof(bytearray(b'Synthetic later reset')))
                    assert actual.reset(again,idempotency_key=str(uuid4())).credential_version==4
                elif kind=='license_withdraw':v['guard'].enabled=False
                snapshots.append(snap());return matched
        hooked=r.SqlAlchemyPasswordResetResults(verifier=HookVerifier());command=cmd(session,target.user_id)
        try:
            got=service(hooked,NoFreshHash()).reset(command,idempotency_key=key)
        except PasswordResetError as exc:
            assert kind in ('role_withdraw','logout','renew','license_withdraw')
            assert exc.code==('LICENSE_OPERATION_DENIED' if kind=='license_withdraw' else 'AUTH_ACCESS_DENIED'),(kind,exc.code)
        else:assert kind in ('normal','target_later_reset') and got==first
        finally:v['guard'].enabled=True
        assert checks==[True] and snap()==snapshots[0] and not any(command.password.temporary_password)
    # Actual first committed by another invocation after outer preparation MISS.
    for i,wrong in enumerate((False,True)):
        target=create(f'Synthetic history race {i}')
        admin=type('Admin',(),{'token':v['tokens'][1],'csrf_token':m.fixture.base.auth.CSRF})()
        key=str(uuid4());committed=[];snapshots=[];hash_calls=[]
        class RacingHasher:
            def hash_password(self,password):
                hashed=hasher.hash_password(password);hash_calls.append(True)
                first=actual.reset(cmd(admin,target.user_id,b'Synthetic different temporary' if wrong else temporary),idempotency_key=key)
                committed.append(first);snapshots.append(snap());return hashed
        command=cmd(admin,target.user_id)
        try:got=service(hash_source=RacingHasher()).reset(command,idempotency_key=key)
        except PasswordResetError as exc:assert wrong and exc.code=='CONFLICT_IDEMPOTENCY'
        else:assert not wrong and got==committed[0]
        assert hash_calls==[True] and len(committed)==1 and snap()==snapshots[0] and not any(command.password.temporary_password)
    print('PASS actual reset history: original first after real change3; real KDF outside deployment/caller/Session locks, no new hash; role withdrawal/logout/renew/License deny without extra writes; subsequent real reset4 preserves original replay. Actual first appears after MISS: one bounded reprepare returns original or wrong-password conflict, nine tables unchanged after other commit, buffers erased. Roles TEST_ONLY/License synthetic; no performance claim.')


if __name__=='__main__':m.fixture.main(exercise=lambda v:(exercise(v),r.exercise(v)))
