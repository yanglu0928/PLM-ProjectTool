"""Real PG/Scrypt historical reset password; TEST_ONLY reset transition, no reset service."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace
from uuid import uuid4
from sqlalchemy import select,insert,update,func
from psycopg import sql
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow,PasswordCredentialRow
from plm_assistant.modules.auth.infrastructure.session_orm import SessionRow
from plm_assistant.modules.auth.infrastructure.password_reset_result_repository import SqlAlchemyPasswordResetResults
from plm_assistant.modules.auth.application.password_reset_result import PasswordResetResult
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetProof,PasswordResetReplayVerifier,PasswordResetReplayError

spec=spec_from_file_location('_reset_source_atomic_change',Path(__file__).resolve().parents[1]/'aut-04-a12-p04-a02-password-change-atomic'/'verify.py')
a=module_from_spec(spec);spec.loader.exec_module(a);m=a.m


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    createfirst=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=createfirst,replay_verifier=m.UserCreateReplayVerifier(source=createfirst),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    old=b'Synthetic reset original password';temporary='Synthetic 临时重置密码'.encode();normal=b'Synthetic after change password'
    def create(name):return creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),
        name,bytearray(old)),idempotency_key=str(uuid4()))
    target=create('Synthetic real reset source');uid=target.user_id
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    def issue(user,password):return sessions.issue(user_id=user,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password)))
    initial=issue(uid,old);repo=SqlAlchemyPasswordResetResults(verifier=hasher)
    def transition(tx,user,hashed):
        previous,oldid,version,state=tx.session.execute(select(UserRow.lock_version,UserRow.active_password_credential_id,
            UserRow.credential_version,UserRow.state).where(UserRow.user_id==user).with_for_update()).one()
        actor=v['users'][1]
        newid=tx.session.execute(insert(PasswordCredentialRow).values(user_id=user,credential_version=version+1,
            password_hash=hashed.password_hash,algorithm_id=hashed.algorithm_id,parameter_set=dict(hashed.parameter_set),
            must_change_password=True,changed_by=actor).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        changed=tx.session.execute(update(UserRow).where(UserRow.user_id==user).values(active_password_credential_id=newid,
            credential_version=version+1,lock_version=previous+1,updated_by=actor,updated_at=func.statement_timestamp())
            .returning(UserRow.updated_at)).scalar_one()
        count=tx.session.execute(update(SessionRow).where(SessionRow.user_id==user,SessionRow.revoked_at.is_(None))
            .values(revoked_at=changed,revoke_reason='PASSWORD_RESET',lock_version=SessionRow.lock_version+1)).rowcount
        trace=uuid4();event=v['audit'].append(tx,m.fixture.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',
            target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
            action='PASSWORD_RESET',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
            target_object_id=user,before_state=f'CREDENTIAL_V{version}',after_state=f'CREDENTIAL_V{version+1}'))
        return PasswordResetResult(uuid4(),user,actor,oldid,newid,version,version+1,previous,previous+1,state,
            event,trace,count,changed,changed)
    with memoryview(temporary) as password:hashed=hasher.hash_password(password)
    with v['uow']() as tx:
        draft=transition(tx,uid,hashed);first=repo.record(tx,draft=draft)
        assert first.accepted_at>=draft.changed_at and first.accepted_at!=draft.accepted_at
        assert repo.get(tx,result_id=first.result_id)==first
        tx.commit()
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def match(password,code=None,source=repo,result=first):
        before=snap();proof=PasswordResetProof(bytearray(password))
        with v['uow']() as tx:
            try:got=PasswordResetReplayVerifier(source=source).require_match(tx,result=result,proof=proof)
            except PasswordResetReplayError as exc:assert exc.code==code,(exc.code,code)
            else:assert code is None and got==result
        assert not any(proof.temporary_password) and snap()==before
    match(temporary)
    for wrong in (old,temporary+b' ',b'wrong',normal):match(wrong,'CONFLICT_IDEMPOTENCY')
    for bad in (replace(first,result_id=uuid4()),replace(first,user_id=uuid4()),replace(first,actor_id=uuid4()),
        replace(first,trace_id=uuid4()),replace(first,credential_id=uuid4()),replace(first,target_state='DISABLED'),
        replace(first,revoked_session_count=first.revoked_session_count+1)):
        match(temporary,'AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE',result=bad)
    class BadKdf:
        def verify_password(self,*args,**kwargs):raise RuntimeError('Synthetic private verifier')
    class TruthyKdf:
        def verify_password(self,*args,**kwargs):return 1
    for kdf in (BadKdf(),TruthyKdf()):match(temporary,'AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE',source=SqlAlchemyPasswordResetResults(verifier=kdf))
    with v['uow']() as tx:assert repo.get(tx,result_id=uuid4()) is None
    # Actual implemented change service normalizes the restricted reset fixture; historical reset still refers Credential2.
    restricted=issue(uid,temporary)
    change_results=a.SqlAlchemyPasswordChangeResults(verifier=hasher)
    change=a.PasswordChangeService(unit_of_work=v['uow'],access=a.SqlAlchemyPasswordChangeAccess(verifier=hasher),
        repository=a.SqlAlchemyPasswordChangeRepository(),results=change_results,
        replay_verifier=a.PasswordChangeReplayVerifier(source=change_results),hasher=hasher,audit=v['audit'],receipts=receipts)
    changed=change.change(a.ChangePassword(restricted.token,restricted.csrf_token,uuid4(),
        a.PasswordChangeProof(bytearray(temporary),bytearray(normal))),idempotency_key=str(uuid4()))
    assert changed.credential_version==3
    fresh=issue(uid,normal);match(temporary);match(normal,'CONFLICT_IDEMPOTENCY')
    before=snap()
    try:
        with v['uow']() as tx:repo.record(tx,draft=replace(draft,result_id=uuid4()))
    except PasswordResetReplayError:pass
    else:raise AssertionError('Historical reset first reinserted')
    assert snap()==before
    # Bad new profile refuses record before persistence, after caller has really changed root/Session/Audit.
    badhash=replace(hashed,parameter_set={'n':-1})
    try:
        with v['uow']() as tx:repo.record(tx,draft=transition(tx,uid,badhash))
    except PasswordResetReplayError:pass
    else:raise AssertionError('Bad new profile recorded')
    assert snap()==before and sessions.validate(fresh.token).user_id==uid
    reached=False
    try:
        with v['uow']() as tx:
            legitimate=repo.record(tx,draft=transition(tx,uid,hashed));reached=True
            assert legitimate.credential_version==4
            raise RuntimeError('Synthetic post-record caller fault')
    except RuntimeError:pass
    assert reached and snap()==before and sessions.validate(fresh.token).user_id==uid
    print('PASS real reset source: actual caller-UOW record/get server acceptedAt and original Credential2 PG/Scrypt match; password differences/forged first/KDF exception-truthy refuse nine tables unchanged/buffers erased. Later actual restricted change→normal Credential3/new login retains original temporary replay; bad new profile and legitimate record then caller fault roll back root/Session/Audit/first, current Session preserved. TEST_ONLY reset transition, NOT Admin-CSRF-License/IfMatch/atomic reset/receipt/HTTP/package proof.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
