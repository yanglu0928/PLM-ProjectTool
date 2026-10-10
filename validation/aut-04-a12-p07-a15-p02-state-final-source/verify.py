"""Actual self-disable final authorization faults and whole-UOW rollback."""
import hashlib
from dataclasses import replace
from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from sqlalchemy import insert, update, text
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.auth.application.user_state import UserStateService, UserStateError, ChangeUserState
from plm_assistant.modules.auth.infrastructure.user_state_access import SqlAlchemyUserStateAccess
from plm_assistant.modules.auth.infrastructure.user_state_repository import SqlAlchemyUserStateRepository
from plm_assistant.modules.auth.infrastructure.user_state_result_repository import SqlAlchemyUserStateResultRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.auth.infrastructure.session_orm import SessionRow

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_self_state_atomic', ROOT / 'validation' /
                              'aut-04-a12-p05-a05-reset-atomic' / 'verify.py')
r = module_from_spec(spec)
spec.loader.exec_module(r)
m = r.m


def exercise(v):
    db, hasher = v['db'], m.ScryptPasswordHasher()
    receipts = m.SqlAlchemyIdempotencyReceipts()
    firsts = m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator = m.ManagedUserCreateService(unit_of_work=v['uow'], access=m.SqlAlchemyUserCreateAccess(),
        license_guard=v['guard'], users=m.SqlAlchemyUserRepository(), results=firsts,
        replay_verifier=m.UserCreateReplayVerifier(source=firsts), hasher=hasher,
        audit=v['audit'], receipts=receipts)
    password = b'Synthetic self state'
    uid = creator.create(m.CreateManagedUser(v['tokens'][1], m.fixture.base.auth.CSRF, uuid4(),
        'Synthetic self state Admin', bytearray(password)), idempotency_key=str(uuid4())).user_id
    # TEST_ONLY trusted role provision, not a production role-management feature.
    db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s", (uid,))
    sessions = m.SessionService(unit_of_work=v['uow'], repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher), audit=v['audit'], idempotency=receipts)
    active = sessions.issue(user_id=uid, trace_id=uuid4(), proof=m.PasswordIssueProof(bytearray(password)))
    version = db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s', (uid,)).fetchone()[0]
    access = SqlAlchemyUserStateAccess()
    repository = SqlAlchemyUserStateRepository()
    deps = dict(unit_of_work=v['uow'], repository=repository, results=SqlAlchemyUserStateResultRepository(),
                audit=v['audit'], receipts=receipts, license_guard=v['guard'])
    tables = ('auth_users', 'auth_password_credentials', 'auth_sessions', 'auth_user_create_results',
              'auth_user_state_results', 'auth_password_change_results', 'auth_password_reset_results',
              'aud_events', 'plt_idempotency_receipts')

    def snapshot():
        return {table: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(
            sql.Identifier(table)))) for table in tables}

    before = snapshot()
    with v['uow']() as tx:
        try:
            repository.change(tx, user_id=uuid4(), actor_id=uid, expected_version=0, operation='DISABLE')
        except UserStateError as exc:
            assert exc.code == 'RESOURCE_NOT_FOUND'
        else:
            raise AssertionError('Missing User changed')
    assert snapshot() == before

    for fault in ('missing_session', 'expired_time', 'credential_proof', 'csrf',
                  'user_version', 'live_session', 'other_admin', 'aborted_transaction'):
        marks = []

        class FaultAccess:
            def __getattr__(self, name):
                return getattr(access, name)

            def require_self_disabled(self, tx, **kwargs):
                assert access.require_self_disabled(tx, **kwargs) is True
                marks.append('positive')
                changed = dict(kwargs)
                proof, result, now = kwargs['proof'], kwargs['result'], kwargs['now']
                if fault == 'missing_session':
                    changed['command'] = replace(kwargs['command'], session_token=b'x' * 32)
                elif fault == 'expired_time':
                    changed['now'] = proof.session_idle_expires_at
                elif fault == 'credential_proof':
                    changed['proof'] = replace(proof, credential_id=uuid4())
                elif fault == 'csrf':
                    changed['command'] = replace(kwargs['command'], csrf_token=b'x' * 32)
                elif fault == 'user_version':
                    tx.session.execute(update(UserRow).where(UserRow.user_id == uid)
                                       .values(lock_version=UserRow.lock_version + 1))
                elif fault == 'live_session':
                    tx.session.execute(insert(SessionRow).values(user_id=uid,
                        credential_version=result.first_view.credential_version,
                        session_token_digest=hashlib.sha256(uuid4().bytes).digest(),
                        csrf_digest=hashlib.sha256(uuid4().bytes).digest(),
                        created_at=now, last_seen_at=now, idle_expires_at=now + timedelta(hours=1),
                        absolute_expires_at=now + timedelta(hours=2)))
                elif fault == 'other_admin':
                    tx.session.execute(update(UserRow).where(UserRow.user_id == v['users'][1])
                        .values(state='DISABLED', lock_version=UserRow.lock_version + 1))
                else:
                    try:
                        tx.session.execute(text('SELECT 1 / 0'))
                    except DBAPIError as exc:
                        assert exc.orig.sqlstate == '22012'
                        marks.append('sql22012')
                    else:
                        raise AssertionError('SQL transaction not aborted')
                if fault == 'aborted_transaction':
                    try:
                        access.require_self_disabled(tx, **changed)
                    except DBAPIError as exc:
                        assert exc.orig.sqlstate == '25P02'
                        marks.append('sql25P02')
                        raise
                    raise AssertionError('Aborted final authorized')
                assert access.require_self_disabled(tx, **changed) is False
                marks.append('denied')
                return False

        before = snapshot()
        command = ChangeUserState(active.token, active.csrf_token, uuid4(), uid, version)
        try:
            UserStateService(**deps, access=FaultAccess()).disable(command, idempotency_key=str(uuid4()))
        except UserStateError as exc:
            assert exc.code == ('AUTH_STATE_UNAVAILABLE' if fault == 'aborted_transaction'
                                else 'AUTH_ACCESS_DENIED'), (fault, exc.code)
        else:
            raise AssertionError('Fault committed')
        assert marks == (['positive', 'sql22012', 'sql25P02'] if fault == 'aborted_transaction'
                         else ['positive', 'denied']), (fault, marks)
        assert snapshot() == before, (fault, 'nine-table rollback mismatch')
        assert sessions.validate(active.token).user_id == uid

    # Actual normal Service commit after all rollbacks, with exact expected revocation.
    command = ChangeUserState(active.token, active.csrf_token, uuid4(), uid, version)
    result = UserStateService(**deps, access=access).disable(command, idempotency_key=str(uuid4()))
    assert result.first_view.account_state == 'DISABLED' and result.revoked_session_count == 1
    assert db.execute('SELECT revoke_reason FROM plm.auth_sessions WHERE session_id=%s',
                      (active.session_id,)).fetchone() == ('USER_DISABLED',)
    print('PASS actual self-disable final: missing User, eight true-positive-before-fault controls then source/time/CSRF/User/live Session/other Admin refusal or actual SQL22012+25P02; each nine-table full rollback and old Session retained; genuine normal self-disable commits/revokes exact Session. DTO faults explicit, TEST_ONLY Admin role/synthetic trust; no production/coverage/performance claim.')


if __name__ == '__main__':
    m.fixture.main(exercise=exercise)
