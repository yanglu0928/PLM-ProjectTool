"""Real PG historical credential source with real Scrypt, not change service."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace
from uuid import uuid4
from sqlalchemy import select,insert,update,func
from psycopg import sql
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow,PasswordCredentialRow
from plm_assistant.modules.auth.infrastructure.session_orm import SessionRow
from plm_assistant.modules.auth.infrastructure.password_change_result_repository import SqlAlchemyPasswordChangeResults
from plm_assistant.modules.auth.application.password_change_result import PasswordChangeResult
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeProof,PasswordChangeReplayVerifier,PasswordChangeReplayError

spec=spec_from_file_location('_real_change_source',Path(__file__).resolve().parents[1]/'aut-04-a11-p03-user-state-atomic'/'verify.py')
m=module_from_spec(spec);spec.loader.exec_module(m)


def exercise(v):
    db=v['db'];hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    createfirst=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=createfirst,replay_verifier=m.UserCreateReplayVerifier(source=createfirst),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    old=b'Synthetic old source password';new='Synthetic 新密码'.encode('utf-8')
    target=creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),
        'Synthetic real change source',bytearray(old)),idempotency_key=str(uuid4()))
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    sessions.issue(user_id=target.user_id,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(old)))
    repo=SqlAlchemyPasswordChangeResults(verifier=hasher);replay=PasswordChangeReplayVerifier(source=repo)
    # TEST_ONLY transition sources in caller UOW; not a current-auth password change service.
    with memoryview(new) as view:hashed=hasher.hash_password(view)
    with v['uow']() as tx:
        uid=target.user_id
        oldid=tx.session.execute(select(UserRow.active_password_credential_id).where(UserRow.user_id==uid).with_for_update()).scalar_one()
        newid=tx.session.execute(insert(PasswordCredentialRow).values(user_id=uid,credential_version=2,
            password_hash=hashed.password_hash,algorithm_id=hashed.algorithm_id,parameter_set=dict(hashed.parameter_set),
            must_change_password=False,changed_by=uid).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        changed=tx.session.execute(update(UserRow).where(UserRow.user_id==uid).values(active_password_credential_id=newid,
            credential_version=2,lock_version=2,updated_by=uid,updated_at=func.statement_timestamp()).returning(UserRow.updated_at)).scalar_one()
        count=tx.session.execute(update(SessionRow).where(SessionRow.user_id==uid,SessionRow.revoked_at.is_(None))
            .values(revoked_at=changed,revoke_reason='PASSWORD_CHANGED',lock_version=SessionRow.lock_version+1)).rowcount
        trace=uuid4();event=v['audit'].append(tx,m.fixture.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',
            target_project_id=None,actor_type='USER',actor_id=uid,original_actor_id=None,actor_hint_digest=None,
            action='PASSWORD_CHANGED',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
            target_object_id=uid,before_state='CREDENTIAL_V1',after_state='CREDENTIAL_V2'))
        draft=PasswordChangeResult(uuid4(),uid,oldid,newid,1,2,1,2,event,trace,count,changed,changed)
        first=repo.record(tx,draft=draft)
        assert first.accepted_at>=changed and first.accepted_at!=draft.accepted_at
        tx.commit()
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def match(before,after,code=None,source=repo,result=first):
        original=snap();proof=PasswordChangeProof(bytearray(before),bytearray(after))
        with v['uow']() as tx:
            try:got=PasswordChangeReplayVerifier(source=source).require_match(tx,result=result,proof=proof)
            except PasswordChangeReplayError as exc:assert code==exc.code,(code,exc.code)
            else:assert code is None and got==first
        assert proof.current_password==bytearray(len(before)) and proof.new_password==bytearray(len(after))
        assert snap()==original
    match(old,new)
    for before,after in ((new,new),(old,old),(old,new+b' '),(b'wrong',new)):
        match(before,after,'CONFLICT_IDEMPOTENCY')
    for forged in (replace(first,result_id=uuid4()),replace(first,user_id=uuid4()),
        replace(first,trace_id=uuid4()),replace(first,before_credential_id=uuid4()),
        replace(first,credential_id=uuid4()),replace(first,revoked_session_count=first.revoked_session_count+1)):
        match(old,new,'AUTH_PASSWORD_REPLAY_UNAVAILABLE',result=forged)
    with v['uow']() as tx:assert repo.get(tx,result_id=uuid4()) is None
    class BadKdf:
        def verify_password(self,*args,**kwargs):raise RuntimeError('Synthetic private KDF')
    match(old,new,'AUTH_PASSWORD_REPLAY_UNAVAILABLE',source=SqlAlchemyPasswordChangeResults(verifier=BadKdf()))
    class TruthyKdf:
        def verify_password(self,*args,**kwargs):return 1
    match(old,new,'AUTH_PASSWORD_REPLAY_UNAVAILABLE',source=SqlAlchemyPasswordChangeResults(verifier=TruthyKdf()))
    # Later active credential3 changes current login password; history matching stays Credential1/2.
    with memoryview(b'Synthetic later source password') as view:thirdhash=hasher.hash_password(view)
    with v['uow']() as tx:
        third=tx.session.execute(insert(PasswordCredentialRow).values(user_id=uid,credential_version=3,
            password_hash=thirdhash.password_hash,algorithm_id=thirdhash.algorithm_id,parameter_set=dict(thirdhash.parameter_set),
            must_change_password=False,changed_by=uid).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        tx.session.execute(update(UserRow).where(UserRow.user_id==uid).values(active_password_credential_id=third,
            credential_version=3,lock_version=3,updated_by=uid,updated_at=func.statement_timestamp()));tx.commit()
    match(old,new);match(old,b'Synthetic later source password','CONFLICT_IDEMPOTENCY')
    original=snap()
    try:
        with v['uow']() as tx:repo.record(tx,draft=replace(draft,result_id=uuid4()))
    except PasswordChangeReplayError:pass
    else:raise AssertionError('Later current root accepted old first insert')
    assert snap()==original
    original=snap()
    try:
        with v['uow']() as tx:
            bad=tx.session.execute(insert(PasswordCredentialRow).values(user_id=uid,credential_version=4,
                password_hash=thirdhash.password_hash,algorithm_id='SCRYPT',parameter_set={'n':-1},
                must_change_password=False,changed_by=uid).returning(PasswordCredentialRow.password_credential_id,
                PasswordCredentialRow.changed_at)).one()
            malformed=PasswordChangeResult(uuid4(),uid,third,bad[0],3,4,3,4,uuid4(),uuid4(),1,bad[1],bad[1])
            repo.record(tx,draft=malformed)
    except PasswordChangeReplayError as exc:assert exc.code=='AUTH_PASSWORD_REPLAY_UNAVAILABLE'
    else:raise AssertionError('Unsafe KDF parameter metadata recorded')
    assert snap()==original
    # Actual record followed by caller failure rolls back all owned transition sources.
    live=sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(b'Synthetic later source password')))
    with memoryview(b'Synthetic rollback source password') as view:fourthhash=hasher.hash_password(view)
    original=snap();reached=False
    try:
        with v['uow']() as tx:
            fourth=tx.session.execute(insert(PasswordCredentialRow).values(user_id=uid,credential_version=4,
                password_hash=fourthhash.password_hash,algorithm_id=fourthhash.algorithm_id,parameter_set=dict(fourthhash.parameter_set),
                must_change_password=False,changed_by=uid).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
            at=tx.session.execute(update(UserRow).where(UserRow.user_id==uid).values(active_password_credential_id=fourth,
                credential_version=4,lock_version=4,updated_by=uid,updated_at=func.statement_timestamp()).returning(UserRow.updated_at)).scalar_one()
            count=tx.session.execute(update(SessionRow).where(SessionRow.user_id==uid,SessionRow.revoked_at.is_(None))
                .values(revoked_at=at,revoke_reason='PASSWORD_CHANGED',lock_version=SessionRow.lock_version+1)).rowcount
            trace4=uuid4();audit4=v['audit'].append(tx,m.fixture.w.AuditEventDraft(trace_id=trace4,event_scope='DEPLOYMENT',
                target_project_id=None,actor_type='USER',actor_id=uid,original_actor_id=None,actor_hint_digest=None,
                action='PASSWORD_CHANGED',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
                target_object_id=uid,before_state='CREDENTIAL_V3',after_state='CREDENTIAL_V4'))
            recorded=repo.record(tx,draft=PasswordChangeResult(uuid4(),uid,third,fourth,3,4,3,4,audit4,trace4,count,at,at))
            assert repo.get(tx,result_id=recorded.result_id)==recorded
            reached=True
            raise RuntimeError('Synthetic caller failure after real result insert')
    except RuntimeError:assert reached
    assert snap()==original and sessions.validate(live.token).credential_version==3
    print('PASS real password-change source: actual caller-UOW record server acceptedAt/get/unknown, real PG Credential1/2 Scrypt matches both UTF8 passwords; each mismatch/forged first/KDF exception/truthy refuse eight tables unchanged and buffers erased; later Credential3 not used for historical replay and rejects old first reinsertion. TEST_ONLY transition, not current-auth/atomic change/receipt/HTTP/package proof.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
