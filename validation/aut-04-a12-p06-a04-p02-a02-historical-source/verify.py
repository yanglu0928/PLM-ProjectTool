"""Actual reset/change history, detached KDF and fresh source recheck."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from dataclasses import replace
from uuid import uuid4
from psycopg import sql
from sqlalchemy import text
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetReplayError
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeReplayError

spec=spec_from_file_location('_detached_reset',Path(__file__).resolve().parents[1]/'aut-04-a12-p05-a05-reset-atomic'/'verify.py')
r=module_from_spec(spec);spec.loader.exec_module(r);m=r.m;a=r.a


def exercise(v):
    hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts();db=v['db']
    creates=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=creates,replay_verifier=m.UserCreateReplayVerifier(source=creates),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    old=b'Synthetic detached original';temporary=b'Synthetic detached temporary';normal=b'Synthetic detached normal';later=b'Synthetic detached later'
    user=creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),'Synthetic detached history',bytearray(old)),idempotency_key=str(uuid4()))
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    reset_results=r.SqlAlchemyPasswordResetResults(verifier=hasher)
    reset=r.PasswordResetService(unit_of_work=v['uow'],access=r.SqlAlchemyPasswordResetAccess(verifier=hasher),repository=r.SqlAlchemyPasswordResetRepository(),
        results=reset_results,replay_verifier=r.PasswordResetReplayVerifier(source=reset_results),hasher=hasher,audit=v['audit'],receipts=receipts,license_guard=v['guard'])
    first_reset=reset.reset(r.ResetPassword(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),user.user_id,1,True,r.PasswordResetProof(bytearray(temporary))),idempotency_key=str(uuid4()))
    change_results=a.SqlAlchemyPasswordChangeResults(verifier=hasher)
    change=a.PasswordChangeService(unit_of_work=v['uow'],access=a.SqlAlchemyPasswordChangeAccess(verifier=hasher),repository=a.SqlAlchemyPasswordChangeRepository(),
        results=change_results,replay_verifier=a.PasswordChangeReplayVerifier(source=change_results),hasher=hasher,audit=v['audit'],receipts=receipts)
    def change_to(before,after):
        session=sessions.issue(user_id=user.user_id,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(before)))
        return change.change(a.ChangePassword(session.token,session.csrf_token,uuid4(),a.PasswordChangeProof(bytearray(before),bytearray(after))),idempotency_key=str(uuid4()))
    first_change=change_to(temporary,normal)
    with v['uow']() as tx:
        tx.session.execute(text('SET TRANSACTION READ ONLY'))
        reset_source=reset_results.password_source(tx,result=first_reset)
        before_source=change_results.password_source(tx,result=first_change,role='BEFORE')
        after_source=change_results.password_source(tx,result=first_change,role='AFTER')
    assert change_to(normal,later).credential_version==4
    checks=[]
    class IndependentVerifier:
        def verify_password(self,password,**kwargs):
            with db.transaction():
                assert db.execute('SELECT pg_try_advisory_xact_lock(1347177793,1431524436)').fetchone()==(True,)
                assert db.execute('SELECT user_id FROM plm.auth_users WHERE user_id=%s FOR UPDATE NOWAIT',(user.user_id,)).fetchone()==(user.user_id,)
                db.execute('SELECT password_credential_id FROM plm.auth_password_credentials WHERE user_id=%s FOR UPDATE NOWAIT',(user.user_id,)).fetchall()
            checks.append(True)
            return hasher.verify_password(password,**kwargs)
    detached_reset=r.SqlAlchemyPasswordResetResults(verifier=IndependentVerifier())
    detached_change=a.SqlAlchemyPasswordChangeResults(verifier=IndependentVerifier())
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results','auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    snapshot=snap()
    for repo,source,password in ((detached_reset,reset_source,temporary),(detached_change,before_source,temporary),(detached_change,after_source,normal)):
        with memoryview(password) as secret:assert repo.verify_password_source(source=source,password=secret) is True
        with memoryview(later) as secret:assert repo.verify_password_source(source=source,password=secret) is False
    assert len(checks)==6 and snap()==snapshot
    # No KDF may run during final source recheck. No actual current authority is inferred.
    class NoKdf:
        def verify_password(self,*args,**kwargs):raise AssertionError('KDF in source recheck')
    reset_check=r.SqlAlchemyPasswordResetResults(verifier=NoKdf());change_check=a.SqlAlchemyPasswordChangeResults(verifier=NoKdf())
    with v['uow']() as tx:
        tx.session.execute(text('SET TRANSACTION READ ONLY'))
        reset_check.require_password_source(tx,result=first_reset,source=reset_source)
        change_check.require_password_source(tx,result=first_change,role='BEFORE',source=before_source)
        change_check.require_password_source(tx,result=first_change,role='AFTER',source=after_source)
        for repo,result,source,role,error in ((reset_check,first_reset,after_source,{},PasswordResetReplayError),
                (change_check,first_change,after_source,{'role':'BEFORE'},PasswordChangeReplayError),
                (change_check,first_change,before_source,{'role':'AFTER'},PasswordChangeReplayError)):
            try:repo.require_password_source(tx,result=result,source=source,**role)
            except error:pass
            else:raise AssertionError('Wrong historical source accepted')
        for repo,result,source,role,error in ((reset_check,first_reset,reset_source,{},PasswordResetReplayError),
                (change_check,first_change,after_source,{'role':'AFTER'},PasswordChangeReplayError)):
            try:repo.require_password_source(tx,result=replace(result,trace_id=uuid4()),source=source,**role)
            except error:pass
            else:raise AssertionError('Forged first accepted')
    assert snap()==snapshot
    print('PASS actual PG/Scrypt detached history: genuine reset2/change3/later4, closed READ ONLY source UOW, exact historical passwords true/latest false; global/User/all Credential independent locks available, six real KDF; fresh READ ONLY full-first/source no KDF, role/source/forged first denied, nine tables unchanged. Service orchestration/performance not yet changed; License synthetic.')


if __name__=='__main__':m.fixture.main(exercise=lambda v:(exercise(v),r.exercise(v)))
