"""Owned temporary DB reproduction of must-change enforcement gap, not PASS."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import insert,select,update
from plm_assistant.modules.auth.infrastructure.user_orm import PasswordCredentialRow,UserRow
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess

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
        assert required is True and admin==user.user_id
    assert v['db'].execute('SELECT count(*) FROM plm.auth_password_credentials WHERE user_id=%s',(user.user_id,)).fetchone()==(2,)
    print('CONFIRMED GAP (NOT SECURITY PASS): actual PG credential2 must_change_password=true + real Scrypt password issuance/validation still grants original DeploymentAdmin-CSRF proof. Explicit TEST_ONLY role and pending reset source; original credential1 preserved. Reset/change routes remain absent; production enforcement prerequisite required. Temporary DB only, no formal credentials/data.')


if __name__=='__main__':m.fixture.main(exercise=exercise)
