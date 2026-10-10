"""Real PostgreSQL final authorization faults and whole-transaction rollback."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from datetime import timedelta
from uuid import uuid4
import hashlib

from psycopg import sql
from sqlalchemy import insert, update, text
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.auth.infrastructure.session_orm import SessionRow
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.auth.infrastructure.password_change_access import PasswordChangeAccessError
from plm_assistant.modules.auth.infrastructure.password_reset_access import PasswordResetAccessError

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_current_final_atomic', ROOT / 'validation' /
                              'aut-04-a12-p05-a05-reset-atomic' / 'verify.py')
r = module_from_spec(spec)
spec.loader.exec_module(r)
m, a = r.m, r.a


def exercise(v):
    db = v['db']
    hasher = m.ScryptPasswordHasher()
    receipts = m.SqlAlchemyIdempotencyReceipts()
    firsts = m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator = m.ManagedUserCreateService(unit_of_work=v['uow'], access=m.SqlAlchemyUserCreateAccess(),
        license_guard=v['guard'], users=m.SqlAlchemyUserRepository(), results=firsts,
        replay_verifier=m.UserCreateReplayVerifier(source=firsts), hasher=hasher,
        audit=v['audit'], receipts=receipts)
    sessions = m.SessionService(unit_of_work=v['uow'], repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher), audit=v['audit'], idempotency=receipts)
    old, new = b'Synthetic final original', b'Synthetic final replacement'
    tables = ('auth_users', 'auth_password_credentials', 'auth_sessions', 'auth_user_create_results',
              'auth_user_state_results', 'auth_password_change_results', 'auth_password_reset_results',
              'aud_events', 'plt_idempotency_receipts')

    def snapshot():
        return {table: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(table))))
                for table in tables}

    passed = []
    for kind in ('change', 'self_reset'):
        created = creator.create(m.CreateManagedUser(v['tokens'][1], m.fixture.base.auth.CSRF, uuid4(),
            'Synthetic final ' + kind, bytearray(old)), idempotency_key=str(uuid4()))
        uid = created.user_id
        if kind == 'self_reset':
            # TEST_ONLY trusted role provision; all subsequent writes use actual Service.
            db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s", (uid,))
        session = sessions.issue(user_id=uid, trace_id=uuid4(), proof=m.PasswordIssueProof(bytearray(old)))
        expected = db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s', (uid,)).fetchone()[0]
        if kind == 'change':
            access = a.SqlAlchemyPasswordChangeAccess(verifier=hasher)
            results = a.SqlAlchemyPasswordChangeResults(verifier=hasher)
            deps = dict(unit_of_work=v['uow'], access=access, repository=a.SqlAlchemyPasswordChangeRepository(),
                results=results, replay_verifier=a.PasswordChangeReplayVerifier(source=results),
                hasher=hasher, audit=v['audit'], receipts=receipts)
            service_type, error_type = a.PasswordChangeService, a.PasswordChangeError
        else:
            access = r.SqlAlchemyPasswordResetAccess(verifier=hasher)
            results = r.SqlAlchemyPasswordResetResults(verifier=hasher)
            deps = dict(unit_of_work=v['uow'], access=access, repository=r.SqlAlchemyPasswordResetRepository(),
                results=results, replay_verifier=r.PasswordResetReplayVerifier(source=results),
                hasher=hasher, audit=v['audit'], receipts=receipts, license_guard=v['guard'])
            service_type, error_type = r.PasswordResetService, r.PasswordResetError

        def command():
            if kind == 'change':
                return a.ChangePassword(session.token, session.csrf_token, uuid4(),
                                        a.PasswordChangeProof(bytearray(old), bytearray(new)))
            return r.ResetPassword(session.token, session.csrf_token, uuid4(), uid, expected, True,
                                   r.PasswordResetProof(bytearray(new)))

        def erased(cmd):
            if kind == 'change':
                return not any(cmd.passwords.current_password) and not any(cmd.passwords.new_password)
            return not any(cmd.password.temporary_password)

        for fault in ('live_session', 'revoked_count', 'user_version', 'aborted_transaction'):
            marks = []
            actual_final = access.require_changed if kind == 'change' else access.require_self_reset

            class FaultAccess:
                def __getattr__(self, name):
                    return getattr(access, name)

                def final(self, tx, **kwargs):
                    # Actual successful SQL final control before injecting real DB facts.
                    assert actual_final(tx, **kwargs) is True
                    marks.append('positive')
                    result = kwargs['result']
                    if fault in ('live_session', 'revoked_count'):
                        fields = dict(user_id=uid, credential_version=result.credential_version,
                            session_token_digest=hashlib.sha256(uuid4().bytes).digest(),
                            csrf_digest=hashlib.sha256(uuid4().bytes).digest(),
                            created_at=result.changed_at, last_seen_at=result.changed_at,
                            idle_expires_at=result.changed_at + timedelta(hours=1),
                            absolute_expires_at=result.changed_at + timedelta(hours=2))
                        if fault == 'revoked_count':
                            fields |= dict(revoked_at=result.changed_at,
                                revoke_reason='PASSWORD_CHANGED' if kind == 'change' else 'PASSWORD_RESET',
                                lock_version=1)
                        tx.session.execute(insert(SessionRow).values(**fields))
                    elif fault == 'user_version':
                        tx.session.execute(update(UserRow).where(UserRow.user_id == uid)
                                           .values(lock_version=UserRow.lock_version + 1))
                    else:
                        try:
                            tx.session.execute(text('SELECT 1 / 0'))
                        except DBAPIError as exc:
                            assert exc.orig.sqlstate == '22012'
                            marks.append('sql22012')
                        else:
                            raise AssertionError('Real division error absent')
                    if fault == 'aborted_transaction':
                        try:
                            actual_final(tx, **kwargs)
                        except (PasswordChangeAccessError, PasswordResetAccessError) as exc:
                            assert str(exc) == ('AUTH_PASSWORD_ACCESS_UNAVAILABLE' if kind == 'change'
                                                else 'AUTH_PASSWORD_RESET_ACCESS_UNAVAILABLE')
                            marks.append('fixed_error')
                            raise
                        raise AssertionError('Aborted transaction authorized')
                    assert actual_final(tx, **kwargs) is False
                    marks.append('denied')
                    return False

                def require_changed(self, tx, **kwargs):
                    return self.final(tx, **kwargs)

                def require_self_reset(self, tx, **kwargs):
                    return self.final(tx, **kwargs)

            before = snapshot()
            cmd = command()
            service = service_type(**(deps | {'access': FaultAccess()}))
            try:
                method = service.change if kind == 'change' else service.reset
                method(cmd, idempotency_key=str(uuid4()))
            except error_type as exc:
                expected_code = ('AUTH_PASSWORD_CHANGE_UNAVAILABLE' if kind == 'change'
                                 else 'AUTH_PASSWORD_RESET_UNAVAILABLE') if fault == 'aborted_transaction' else 'AUTH_ACCESS_DENIED'
                assert exc.code == expected_code, (kind, fault, exc.code)
            else:
                raise AssertionError('Fault committed')
            assert marks == (['positive', 'sql22012', 'fixed_error'] if fault == 'aborted_transaction'
                             else ['positive', 'denied']), (kind, fault, marks)
            assert snapshot() == before, (kind, fault, 'nine-table rollback mismatch')
            assert sessions.validate(session.token).user_id == uid and erased(cmd)
            passed.append((kind, fault))

        # Genuine successful commit after rollback, not a disabled final verifier.
        cmd = command()
        service = service_type(**deps)
        method = service.change if kind == 'change' else service.reset
        first = method(cmd, idempotency_key=str(uuid4()))
        assert first.credential_version == 2 and erased(cmd)
        fresh = sessions.issue(user_id=uid, trace_id=uuid4(), proof=m.PasswordIssueProof(bytearray(new)))
        assert sessions.validate(fresh.token).credential_version == 2
    assert len(passed) == 8
    print('PASS actual final: change/self-reset each real positive final then live Session/count/User version reject; SQL22012 aborted UOW fixed error; eight complete nine-table rollbacks, old Session retained/buffers erased; two genuine commit/new Session controls. Synthetic trust/TEST_ONLY role, no production/performance/full-security claim.')


if __name__ == '__main__':
    m.fixture.main(exercise=exercise)
