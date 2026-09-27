"""Real PG SELECT-only receipt visibility; isolated owned fixture, synthetic data."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from sqlalchemy import text
from plm_assistant.modules.platform.application.idempotency import IdempotencyError, IdempotencyResult, IdempotencyScope
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts

spec = spec_from_file_location('_hint_fixture', Path(__file__).resolve().parents[1] / 'aut-04-a12-p06-a02-reset-prehash' / 'verify.py')
r = module_from_spec(spec); spec.loader.exec_module(r)


def exercise(v):
    receipts = SqlAlchemyIdempotencyReceipts()
    scope = IdempotencyScope(v['users'][1], None, 'V1_AUTH_HINT_TEST', uuid4().bytes*2)
    result = IdempotencyResult('V1_AUTH_HINT_TEST', uuid4(), 200)
    fp = b'f'*32
    tables = ('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
              'auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():
        return {t: tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def lookup(s=scope, fingerprint=fp):
        with v['uow']() as tx:
            tx.session.execute(text('SET TRANSACTION READ ONLY'))
            tx.session.execute(text("SET LOCAL lock_timeout='500ms'"))
            return receipts.lookup_completed(tx, scope=s, request_fingerprint=fingerprint)
    before = snap()
    assert lookup() is None and snap() == before
    with v['uow']() as writer:
        assert receipts.reserve(writer, scope=scope, request_fingerprint=fp) is None
        receipts.complete(writer, scope=scope, result=result)
        assert lookup() is None  # Other connection cannot see uncommitted completion.
    assert lookup() is None and snap() == before  # Rolled back.
    with v['uow']() as writer:
        assert receipts.reserve(writer, scope=scope, request_fingerprint=fp) is None
        receipts.complete(writer, scope=scope, result=result)
        assert lookup() is None
        writer.commit()
    before = snap()
    with v['db'].transaction():
        v['db'].execute('SELECT receipt_id FROM plm.plt_idempotency_receipts WHERE key_digest=%s FOR UPDATE', (scope.key_digest,))
        for _ in range(20):
            assert lookup() == result  # Plain SELECT does not wait on held row lock.
    for s in (IdempotencyScope(uuid4(), None, scope.operation, scope.key_digest),
              IdempotencyScope(scope.actor_id, uuid4(), scope.operation, scope.key_digest),
              IdempotencyScope(scope.actor_id, None, 'V1_AUTH_OTHER_TEST', scope.key_digest),
              IdempotencyScope(scope.actor_id, None, scope.operation, b'z'*32)):
        assert lookup(s) is None
    try: lookup(fingerprint=b'x'*32)
    except IdempotencyError as exc: assert exc.code == 'CONFLICT_IDEMPOTENCY'
    else: raise AssertionError('fingerprint conflict not rejected')
    assert snap() == before
    with v['uow']() as tx:
        assert receipts.reserve(tx, scope=scope, request_fingerprint=fp) == result
    pending = IdempotencyScope(scope.actor_id, None, scope.operation, b'p'*32)
    with v['uow']() as tx:
        assert receipts.reserve(tx, scope=pending, request_fingerprint=fp) is None
        tx.commit()
    before = snap()
    try: lookup(pending)
    except IdempotencyError as exc: assert exc.code == 'SYSTEM_UNAVAILABLE'
    else: raise AssertionError('pending not rejected')
    assert snap() == before
    print('PASS actual PG receipt hint: READ ONLY; absent/uncommitted/rollback invisible; committed exact original; held row lock readable; four scope boundaries; fingerprint conflict; pending denied; nine tables unchanged by lookup. No authorization or password performance claim.')


if __name__ == '__main__':
    r.m.fixture.main(exercise=lambda v: (exercise(v), r.exercise(v), r.r.exercise(v)))
