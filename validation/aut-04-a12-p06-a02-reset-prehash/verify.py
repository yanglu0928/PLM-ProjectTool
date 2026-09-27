"""Actual PG locks released during reset KDF and fresh authority after interleavings."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.auth.application.password_reset import ResetPassword,PasswordResetService,PasswordResetError
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof

spec=spec_from_file_location('_reset_preparation_atomic',Path(__file__).resolve().parents[1]/'aut-04-a12-p05-a05-reset-atomic'/'verify.py')
r=module_from_spec(spec);spec.loader.exec_module(r);m=r.m


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    firsts=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=firsts,replay_verifier=m.UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    old=b'Synthetic prehash original';temporary=b'Synthetic prehash temporary'
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),name,
        bytearray(old)),idempotency_key=str(uuid4()))
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    def issue(uid):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(old)))
    results=r.SqlAlchemyPasswordResetResults(verifier=hasher)
    deps=dict(unit_of_work=v['uow'],access=r.SqlAlchemyPasswordResetAccess(verifier=hasher),repository=r.SqlAlchemyPasswordResetRepository(),
        results=results,replay_verifier=r.PasswordResetReplayVerifier(source=results),hasher=hasher,audit=v['audit'],
        receipts=receipts,license_guard=v['guard'])
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    states=m.UserStateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserStateAccess(),repository=m.SqlAlchemyUserStateRepository(),
        results=m.SqlAlchemyUserStateResultRepository(),audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    for index,kind in enumerate(('normal','role_withdraw','logout','renew','target_version','license_withdraw')):
        caller=create(f'Synthetic prehash caller {index}');target=create(f'Synthetic prehash target {index}')
        # TEST_ONLY role provisioning; subsequent Session/KDF/commands are actual.
        db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(caller.user_id,))
        session=issue(caller.user_id);post_interleaving=[];checks=[]
        def hook():
            # db is an independent native PG connection from the completed SQLAlchemy preparation.
            with db.transaction():
                assert db.execute('SELECT pg_try_advisory_xact_lock(1347177793,1431524436)').fetchone()==(True,)
                assert db.execute('SELECT user_id FROM plm.auth_users WHERE user_id=%s FOR UPDATE NOWAIT',(caller.user_id,)).fetchone()==(caller.user_id,)
                assert db.execute('SELECT session_id FROM plm.auth_sessions WHERE session_id=%s FOR UPDATE NOWAIT',(session.session_id,)).fetchone()==(session.session_id,)
                checks.append(True)
            if kind=='role_withdraw':
                db.execute("UPDATE plm.auth_users SET deployment_role='NONE',lock_version=lock_version+1 WHERE user_id=%s",(caller.user_id,))
            elif kind=='logout':
                sessions.logout(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4(),idempotency_key=str(uuid4()))
            elif kind=='renew':
                renewed=sessions.renew(token=session.token,csrf_token=session.csrf_token,trace_id=uuid4())
                assert sessions.validate(renewed.token).user_id==caller.user_id
            elif kind=='target_version':
                states.disable(m.ChangeUserState(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),target.user_id,1),idempotency_key=str(uuid4()))
            elif kind=='license_withdraw':v['guard'].enabled=False
            post_interleaving.append(snap())
        class HookHasher:
            def hash_password(self,password):
                hashed=hasher.hash_password(password);hook();return hashed
        command=ResetPassword(session.token,session.csrf_token,uuid4(),target.user_id,1,True,PasswordResetProof(bytearray(temporary)))
        try:
            result=PasswordResetService(**(deps|{'hasher':HookHasher()})).reset(command,idempotency_key=str(uuid4()))
        except PasswordResetError as exc:
            expected='CONFLICT_VERSION' if kind=='target_version' else 'LICENSE_OPERATION_DENIED' if kind=='license_withdraw' else 'AUTH_ACCESS_DENIED'
            assert kind!='normal' and exc.code==expected,(kind,exc.code)
            assert snap()==post_interleaving[0]
        else:
            assert kind=='normal' and result.credential_version==2 and result.actor_id==caller.user_id
        finally:v['guard'].enabled=True
        assert checks==[True] and not any(command.password.temporary_password)
    print('PASS reset prehash actual PG/Scrypt: independent connection acquires deployment/actor/Session locks during KDF; normal commits; actual role withdrawal/logout/renew/target disable version and synthetic License withdrawal each deny with nine tables unchanged after interleaving; original password buffer erased. Role setup TEST_ONLY; License synthetic; no performance claim.')


if __name__=='__main__':m.fixture.main(exercise=lambda v:(exercise(v),r.exercise(v)))
