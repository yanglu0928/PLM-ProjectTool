"""Actual Review authentication sources and refusal boundaries in an owned PG fixture."""
import hashlib
from datetime import datetime, timezone, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.auth.infrastructure.review_start_access import SqlAlchemyReviewStartAccess

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_review_source_publication', ROOT / 'validation' /
                              'aud-03-a06-a04-p03-a04-p03-publication/verify.py')
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def exercise(v):
    db, uid, token = v['db'], v['users'][0], v['tokens'][0]
    csrf = fixture.base.auth.CSRF
    access = SqlAlchemyReviewStartAccess()
    digest = hashlib.sha256(token).digest()
    created, idle, absolute = db.execute('SELECT created_at,idle_expires_at,absolute_expires_at '
        'FROM plm.auth_sessions WHERE session_token_digest=%s', (digest,)).fetchone()
    tables = ('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results',
              'auth_user_state_results','auth_password_change_results','auth_password_reset_results',
              'aud_events','plt_idempotency_receipts')
    def snapshot():
        return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def healthy():
        before = snapshot()
        with v['uow']() as tx:
            assert access.authenticated_user(tx, session_token=token, csrf_token=csrf,
                                              now=datetime.now(timezone.utc)) == uid
        assert snapshot() == before
    healthy()
    for case in ('unknown_token','wrong_csrf','before_created','idle_expired','absolute_expired',
                 'disabled_user','revoked_session','aborted_transaction'):
        before = snapshot()
        with v['uow']() as tx:
            args = dict(session_token=token, csrf_token=csrf, now=datetime.now(timezone.utc))
            if case == 'unknown_token': args['session_token'] = b'?' * 32
            if case == 'wrong_csrf': args['csrf_token'] = b'?' * 32
            if case == 'before_created': args['now'] = created - timedelta(microseconds=1)
            if case == 'idle_expired': args['now'] = idle
            if case == 'absolute_expired': args['now'] = absolute
            if case == 'disabled_user':
                tx.session.execute(text("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=:uid"), {'uid':uid})
            if case == 'revoked_session':
                tx.session.execute(text("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='ADMIN_REVOKED',lock_version=lock_version+1 WHERE session_token_digest=:digest"), {'digest':digest})
            if case == 'aborted_transaction':
                try:
                    tx.session.execute(text('SELECT 1/0'))
                except DBAPIError as exc:
                    assert exc.orig.sqlstate == '22012'
                else:
                    raise AssertionError('Actual SQL fault did not occur')
                try:
                    access.authenticated_user(tx, **args)
                except DBAPIError as exc:
                    assert exc.orig.sqlstate == '25P02'
                else:
                    raise AssertionError('Aborted SQL authentication accepted')
            else:
                assert access.authenticated_user(tx, **args) is None, case
        assert snapshot() == before, case
        healthy()
        print('REVIEW_SOURCE_RESULT ' + case + ' PASS actual SQL / nine-table rollback / healthy reread')
    print('PASS: actual Review authentication proof and eight refusals, no production trust or Review workflow claim.')


if __name__ == '__main__':
    fixture.main(exercise=exercise)
