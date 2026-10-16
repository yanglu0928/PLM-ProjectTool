"""Actual normal/restricted current Auth and intentional change final proof."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import insert,select,update
from uuid import uuid4
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow,PasswordCredentialRow
from plm_assistant.modules.auth.infrastructure.password_change_access import SqlAlchemyPasswordChangeAccess

spec=spec_from_file_location('_change_actor_source',Path(__file__).resolve().parents[1]/'aut-04-a12-p03-a03-password-change-source'/'verify.py')
source=module_from_spec(spec);spec.loader.exec_module(source)


def exercise(v):
    source.exercise(v,access_checks=True)
    m=source.m;hasher=m.ScryptPasswordHasher();access=SqlAlchemyPasswordChangeAccess(verifier=hasher)
    # Explicit TEST_ONLY restricted Credential; actual Scrypt source, no reset feature claim.
    uid=v['db'].execute("SELECT user_id FROM plm.auth_users WHERE username_display='Synthetic real change source'").fetchone()[0]
    with v['uow']() as tx:
        old=tx.session.execute(select(PasswordCredentialRow).where(PasswordCredentialRow.user_id==uid,
            PasswordCredentialRow.credential_version==3)).scalar_one()
        restricted=tx.session.execute(insert(PasswordCredentialRow).values(user_id=uid,credential_version=4,
            password_hash=old.password_hash,algorithm_id=old.algorithm_id,parameter_set=old.parameter_set,
            must_change_password=True,changed_by=uid).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        tx.session.execute(update(UserRow).where(UserRow.user_id==uid).values(active_password_credential_id=restricted,
            credential_version=4,lock_version=4));tx.commit()
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher),audit=v['audit'],idempotency=m.SqlAlchemyIdempotencyReceipts())
    issued=sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(b'Synthetic later source password')))
    with v['uow']() as tx:
        actor=access.prove(tx,session_token=issued.token,csrf_token=issued.csrf_token,now=datetime.now(timezone.utc))
        assert actor.password_change_required is True and actor.user_view.deployment_role=='NONE'
        with memoryview(b'Synthetic later source password') as password:assert access.verify_current_password(tx,proof=actor,password=password) is True
        assert m.SqlAlchemyUserCreateAccess().authorized_admin(tx,session_token=issued.token,csrf_token=issued.csrf_token,
            now=datetime.now(timezone.utc)) is None
    print('PASS actual password change Auth: normal current Token-CSRF/User/Credential/Scrypt proof and restricted nonAdmin proof; deployment lock; actual first intentional mutation final proof succeeds, forged CSRF/Token/trace/original flag/version/expired original life refuses; old Session no fresh authority. Source/rollback regression retained. TEST_ONLY transition, NOT complete atomic change service/HTTP/package.')


if __name__=='__main__':source.m.fixture.main(exercise=exercise)
