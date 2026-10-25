"""Actual detached current-password KDF and fresh authority across real interleavings."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.auth.application.password_reset import ResetPassword,PasswordResetService
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof,PasswordResetReplayVerifier
from plm_assistant.modules.auth.infrastructure.password_reset_access import SqlAlchemyPasswordResetAccess
from plm_assistant.modules.auth.infrastructure.password_reset_repository import SqlAlchemyPasswordResetRepository
from plm_assistant.modules.auth.infrastructure.password_reset_result_repository import SqlAlchemyPasswordResetResults

spec=spec_from_file_location('_change_preparation_atomic',Path(__file__).resolve().parents[1]/'aut-04-a12-p04-a02-password-change-atomic'/'verify.py')
r=module_from_spec(spec);spec.loader.exec_module(r);m=r.m


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    firsts=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=firsts,replay_verifier=m.UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    old=b'Synthetic detached original';normal=b'Synthetic detached normal'
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),name,
        bytearray(old)),idempotency_key=str(uuid4()))
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    def issue(uid):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(old)))
    results=r.SqlAlchemyPasswordChangeResults(verifier=hasher)
    deps=dict(unit_of_work=v['uow'],access=r.SqlAlchemyPasswordChangeAccess(verifier=hasher),repository=r.SqlAlchemyPasswordChangeRepository(),
        results=results,replay_verifier=r.PasswordChangeReplayVerifier(source=results),hasher=hasher,audit=v['audit'],receipts=receipts)
    reset_results=SqlAlchemyPasswordResetResults(verifier=hasher)
    resets=PasswordResetService(unit_of_work=v['uow'],access=SqlAlchemyPasswordResetAccess(verifier=hasher),
        repository=SqlAlchemyPasswordResetRepository(),results=reset_results,replay_verifier=PasswordResetReplayVerifier(source=reset_results),
        hasher=hasher,audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    states=m.UserStateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserStateAccess(),repository=m.SqlAlchemyUserStateRepository(),
        results=m.SqlAlchemyUserStateResultRepository(),audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    for index,kind in enumerate(('normal','wrong_password','logout','renew','disable','reset','license_disabled','role_change')):
        user=create(f'Synthetic detached user {index}');session=issue(user.user_id);post=[];checks=[]
        def locks():
            with db.transaction():
                assert db.execute('SELECT pg_try_advisory_xact_lock(1347177793,1431524436)').fetchone()==(True,)
                assert db.execute('SELECT user_id FROM plm.auth_users WHERE user_id=%s FOR UPDATE NOWAIT',(user.user_id,)).fetchone()==(user.user_id,)
                assert db.execute('SELECT session_id FROM plm.auth_sessions WHERE session_id=%s FOR UPDATE NOWAIT',(session.session_id,)).fetchone()==(session.session_id,)
                checks.append(True)
        def interleave():
            if kind=='logout':sessions.logout(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4(),idempotency_key=str(uuid4()))
            elif kind=='renew':
                new=sessions.renew(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4())
                assert sessions.validate(new.token).user_id==user.user_id
            elif kind=='disable':states.disable(m.ChangeUserState(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),user.user_id,1),idempotency_key=str(uuid4()))
            elif kind=='reset':resets.reset(ResetPassword(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),user.user_id,1,True,
                PasswordResetProof(bytearray(b'Synthetic concurrent reset'))),idempotency_key=str(uuid4()))
            elif kind=='license_disabled':v['guard'].enabled=False
            elif kind=='role_change':
                # TEST_ONLY role provisioning; actual change must use fresh proof/User version, not stale metadata.
                db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(user.user_id,))
            post.append(snap())
        class HookVerifier:
            def verify_password(self,password,**kwargs):
                matched=hasher.verify_password(password,**kwargs);locks();interleave();return matched
        class HookHasher:
            def hash_password(self,password):locks();return hasher.hash_password(password)
        owner=r.PasswordChangeService(**(deps|{'access':r.SqlAlchemyPasswordChangeAccess(verifier=HookVerifier()),'hasher':HookHasher()}))
        command=r.ChangePassword(session.token,session.csrf_token,uuid4(),r.PasswordChangeProof(
            bytearray(b'Synthetic wrong' if kind=='wrong_password' else old),bytearray(normal)))
        try:result=owner.change(command,idempotency_key=str(uuid4()))
        except r.PasswordChangeError as exc:
            assert kind in ('wrong_password','logout','renew','disable','reset')
            assert exc.code==('AUTH_INVALID_CREDENTIALS' if kind=='wrong_password' else 'AUTH_ACCESS_DENIED'),(kind,exc.code)
            assert snap()==post[0]
        else:
            assert kind in ('normal','license_disabled','role_change') and result.credential_version==2
            assert result.before_user_version==(2 if kind=='role_change' else 1)
        finally:v['guard'].enabled=True
        assert checks==([True] if kind=='wrong_password' else [True,True])
        assert not any(command.passwords.current_password) and not any(command.passwords.new_password)
    print('PASS detached change actual PG/Scrypt: verify/newhash outside global/User/Session locks; actual logout/renew/disable/reset credential races deny and nine tables preserve interleaving only; wrong password denies; normal and License-disabled change succeeds, TEST_ONLY role update uses fresh User version. Original atomic replay/rollback tests follow; no performance claim.')


if __name__=='__main__':m.fixture.main(exercise=lambda v:(exercise(v),r.exercise(v)))
