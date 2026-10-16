"""Owned temporary DB guard for the previously reproduced must-change gap."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import insert,select,update
from psycopg import sql
from plm_assistant.modules.auth.infrastructure.user_orm import PasswordCredentialRow,UserRow
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.review_start_access import SqlAlchemyReviewStartAccess
from plm_assistant.modules.auth.infrastructure.session_credential import SqlAlchemySessionCredentialFacts

spec=spec_from_file_location('_reset_precondition_fixture',Path(__file__).resolve().parents[1]/'aut-04-a11-p03-user-state-atomic'/'verify.py')
m=module_from_spec(spec);spec.loader.exec_module(m)


def exercise(v):
    hasher=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts()
    firsts=m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=firsts,replay_verifier=m.UserCreateReplayVerifier(source=firsts),
        hasher=hasher,audit=v['audit'],receipts=receipts)
    user=creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),
        'Synthetic must-change precondition',bytearray(b'Synthetic temporary reset password')),idempotency_key=str(uuid4()))
    # Explicit TEST_ONLY pending reset source. Append credential2; never mutate credential1.
    with v['uow']() as tx:
        initial=tx.session.execute(select(PasswordCredentialRow).where(PasswordCredentialRow.user_id==user.user_id,
            PasswordCredentialRow.credential_version==1)).scalar_one()
        new=tx.session.execute(insert(PasswordCredentialRow).values(user_id=user.user_id,credential_version=2,
            password_hash=initial.password_hash,algorithm_id=initial.algorithm_id,parameter_set=initial.parameter_set,
            must_change_password=True,changed_by=v['users'][1]).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        tx.session.execute(update(UserRow).where(UserRow.user_id==user.user_id).values(
            active_password_credential_id=new,credential_version=2,lock_version=2,deployment_role='DEPLOYMENT_ADMIN'))
        tx.commit()
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=receipts)
    issued=sessions.issue(user_id=user.user_id,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(b'Synthetic temporary reset password')))
    principal=sessions.validate(issued.token,csrf_token=issued.csrf_token,require_csrf=True)
    assert principal.user_id==user.user_id and principal.credential_version==2
    with v['uow']() as tx:
        required=tx.session.execute(select(PasswordCredentialRow.must_change_password).where(
            PasswordCredentialRow.password_credential_id==new)).scalar_one()
        admin=SqlAlchemyLicenseImportAccess().authorized_admin(tx,session_token=issued.token,
            csrf_token=issued.csrf_token,now=datetime.now(timezone.utc))
        assert required is True and admin is None
    def proofs(token,csrf,expected):
        tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results',
            'auth_user_state_results','aud_events','plt_idempotency_receipts')
        def snap():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        before=snap()
        with v['uow']() as tx:
            now=datetime.now(timezone.utc)
            for adapter,method,kwargs in (
                (SqlAlchemyLicenseImportAccess(),'authorized_admin',dict(csrf_token=csrf)),
                (SqlAlchemyDeploymentReadAccess(),'authorized_admin',{}),
                (SqlAlchemyProjectReadAccess(),'authenticated_user',{}),
                (SqlAlchemyProjectWriteAccess(),'authenticated_user',dict(csrf_token=csrf)),
                (SqlAlchemyReviewStartAccess(),'authenticated_user',dict(csrf_token=csrf))):
                assert getattr(adapter,method)(tx,session_token=token,now=now,**kwargs)==expected
        assert snap()==before
    proofs(issued.token,issued.csrf_token,None)
    proofs(b'?'*32,issued.csrf_token,None)
    with v['uow']() as tx:
        fact=SqlAlchemySessionCredentialFacts().get(tx,session_token=issued.token,now=datetime.now(timezone.utc))
        assert fact.user_id==user.user_id and fact.credential_id==new and fact.credential_version==2
        assert fact.password_change_required is True and not fact.permits('BUSINESS')
        assert all(fact.permits(cap) for cap in ('PASSWORD_STATE','PASSWORD_CHANGE','LOGOUT'))
        assert SqlAlchemySessionCredentialFacts().get(tx,session_token=b'?'*32,now=datetime.now(timezone.utc)) is None
    # TEST_ONLY append a later normal credential; no password-change implementation claimed.
    with v['uow']() as tx:
        active=tx.session.execute(select(PasswordCredentialRow).where(PasswordCredentialRow.password_credential_id==new)).scalar_one()
        third=tx.session.execute(insert(PasswordCredentialRow).values(user_id=user.user_id,credential_version=3,
            password_hash=active.password_hash,algorithm_id=active.algorithm_id,parameter_set=active.parameter_set,
            must_change_password=False,changed_by=user.user_id).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        tx.session.execute(update(UserRow).where(UserRow.user_id==user.user_id).values(
            active_password_credential_id=third,credential_version=3,lock_version=3))
        tx.commit()
    proofs(issued.token,issued.csrf_token,None)
    with v['uow']() as tx:assert SqlAlchemySessionCredentialFacts().get(tx,session_token=issued.token,now=datetime.now(timezone.utc)) is None
    ordinary=sessions.issue(user_id=user.user_id,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(b'Synthetic temporary reset password')))
    proofs(ordinary.token,ordinary.csrf_token,user.user_id)
    with v['uow']() as tx:
        fact=SqlAlchemySessionCredentialFacts().get(tx,session_token=ordinary.token,now=datetime.now(timezone.utc))
        assert fact.password_change_required is False and fact.credential_version==3 and fact.permits('BUSINESS')
    assert v['db'].execute('SELECT count(*) FROM plm.auth_password_credentials WHERE user_id=%s',(user.user_id,)).fetchone()==(3,)
    print('PASS restricted credential core: real PG/Scrypt must-change Session remains identity-only; actual five business Auth proofs refuse, current fact binds credential2; later TEST_ONLY normal credential3 makes old Session invalid and new Session restores five proofs/current normal fact. Credentials preserved. This replaces the earlier confirmed-gap assertion; NOT complete reset/change HTTP or security/UI/package PASS; synthetic roles/credential changes only.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
