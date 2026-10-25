"""Actual change history dual KDF without locks; no cached current authority."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.auth.application.password_change import PasswordChangeError

spec=spec_from_file_location('_change_history_atomic',Path(__file__).resolve().parents[1]/'aut-04-a12-p04-a02-password-change-atomic'/'verify.py')
a=module_from_spec(spec);spec.loader.exec_module(a);m=a.m


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    creates=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=creates,replay_verifier=m.UserCreateReplayVerifier(source=creates),hasher=hasher,audit=v['audit'],receipts=receipts)
    old=b'Synthetic history old';new=b'Synthetic history new';later=b'Synthetic history later'
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),name,bytearray(old)),idempotency_key=str(uuid4()))
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    def issue(uid,password):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password)))
    results=a.SqlAlchemyPasswordChangeResults(verifier=hasher)
    def service(firsts=results,access=None,hash_source=hasher):return a.PasswordChangeService(unit_of_work=v['uow'],access=access or a.SqlAlchemyPasswordChangeAccess(verifier=hasher),
        repository=a.SqlAlchemyPasswordChangeRepository(),results=firsts,replay_verifier=a.PasswordChangeReplayVerifier(source=firsts),hasher=hash_source,audit=v['audit'],receipts=receipts)
    actual=service()
    def cmd(session,before,after):return a.ChangePassword(session.token,session.csrf_token,uuid4(),a.PasswordChangeProof(bytearray(before),bytearray(after)))
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results','auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    class NoCurrent(a.SqlAlchemyPasswordChangeAccess):
        def current_password_source(self,*args,**kwargs):raise AssertionError('Current source in history')
        def verify_password_source(self,*args,**kwargs):raise AssertionError('Current KDF in history')
    class NoHash:
        def hash_password(self,password):raise AssertionError('New hash in history')
    for i,kind in enumerate(('normal','logout','renew','disable','later_change','license_disabled')):
        target=create(f'Synthetic change history {i}');initial=issue(target.user_id,old);key=str(uuid4())
        first=actual.change(cmd(initial,old,new),idempotency_key=key)
        active=issue(target.user_id,new)
        assert actual.change(cmd(active,new,later),idempotency_key=str(uuid4())).credential_version==3
        session=issue(target.user_id,later);checks=[];snapshots=[]
        class HookVerifier:
            def verify_password(self,password,**kwargs):
                matched=hasher.verify_password(password,**kwargs)
                with db.transaction():
                    assert db.execute('SELECT pg_try_advisory_xact_lock(1347177793,1431524436)').fetchone()==(True,)
                    assert db.execute('SELECT user_id FROM plm.auth_users WHERE user_id=%s FOR UPDATE NOWAIT',(target.user_id,)).fetchone()==(target.user_id,)
                    assert db.execute('SELECT session_id FROM plm.auth_sessions WHERE session_id=%s FOR UPDATE NOWAIT',(session.session_id,)).fetchone()==(session.session_id,)
                checks.append(True)
                if len(checks)==2:
                    if kind=='logout':sessions.logout(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4(),idempotency_key=str(uuid4()))
                    elif kind=='renew':sessions.renew(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4())
                    elif kind=='disable':
                        states=m.UserStateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserStateAccess(),repository=m.SqlAlchemyUserStateRepository(),
                            results=m.SqlAlchemyUserStateResultRepository(),audit=v['audit'],receipts=receipts,license_guard=v['guard'])
                        states.disable(m.ChangeUserState(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),target.user_id,3),idempotency_key=str(uuid4()))
                    elif kind=='later_change':assert actual.change(cmd(session,later,b'Synthetic fourth'),idempotency_key=str(uuid4())).credential_version==4
                    elif kind=='license_disabled':v['guard'].enabled=False
                    snapshots.append(snap())
                return matched
        hooked=a.SqlAlchemyPasswordChangeResults(verifier=HookVerifier());command=cmd(session,old,new)
        try:got=service(hooked,NoCurrent(verifier=hasher),NoHash()).change(command,idempotency_key=key)
        except PasswordChangeError as exc:assert kind in ('logout','renew','disable','later_change') and exc.code=='AUTH_ACCESS_DENIED',(kind,exc.code)
        else:assert kind in ('normal','license_disabled') and got==first
        finally:v['guard'].enabled=True
        assert checks==[True,True] and snap()==snapshots[0]
        assert not any(command.passwords.current_password) and not any(command.passwords.new_password)
        if kind=='normal':
            before=snap()
            for left,right in ((old+b' ',new),(old,new+b' ')):
                bad=cmd(session,left,right)
                try:service(results,NoCurrent(verifier=hasher),NoHash()).change(bad,idempotency_key=key)
                except PasswordChangeError as exc:assert exc.code=='CONFLICT_IDEMPOTENCY'
                else:raise AssertionError('Wrong historical password accepted')
                assert snap()==before and not any(bad.passwords.current_password) and not any(bad.passwords.new_password)
    # Real first appears after preparation MISS: successful peer revokes this Session.
    target=create('Synthetic change history race');session=issue(target.user_id,old);key=str(uuid4());committed=[];snapshots=[]
    class RaceAccess(a.SqlAlchemyPasswordChangeAccess):
        def verify_password_source(self,**kwargs):
            matched=super().verify_password_source(**kwargs)
            committed.append(actual.change(cmd(session,old,new),idempotency_key=key));snapshots.append(snap());return matched
    command=cmd(session,old,new)
    try:service(access=RaceAccess(verifier=hasher)).change(command,idempotency_key=key)
    except PasswordChangeError as exc:assert exc.code=='AUTH_ACCESS_DENIED'
    else:raise AssertionError('Revoked peer Session authorized')
    assert len(committed)==1 and snap()==snapshots[0] and not any(command.passwords.current_password) and not any(command.passwords.new_password)
    fresh=issue(target.user_id,new);before=snap()
    assert actual.change(cmd(fresh,old,new),idempotency_key=key)==committed[0] and snap()==before
    print('PASS actual change history: original dual source after real later Credential3; two KDFs independent global/User/Session locks, no current KDF/new hash; wrong before/after conflict; logout/renew/disable/later actual change4 deny, License-disabled valid replay; nine tables unchanged beyond external operations. Real peer first after MISS revokes old Session, outer denied/new current Session recovers original, buffers erased. License synthetic; no performance claim.')


if __name__=='__main__':m.fixture.main(exercise=lambda v:(exercise(v),a.exercise(v)))
