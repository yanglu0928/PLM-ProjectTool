"""Actual initial Credential SQL and full creation rollback with explicit faults."""
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayError
from plm_assistant.modules.auth.application.managed_user_create import ManagedUserCreateError

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_create_result_atomic', ROOT / 'validation' /
                              'aut-04-a12-p05-a05-reset-atomic' / 'verify.py')
r = module_from_spec(spec)
spec.loader.exec_module(r)
m = r.m


def exercise(v):
    db, hasher = v['db'], m.ScryptPasswordHasher()
    receipts = m.SqlAlchemyIdempotencyReceipts()
    repo_type = m.SqlAlchemyUserCreateResultRepository
    repo = repo_type(verifier=hasher)
    deps = dict(unit_of_work=v['uow'], access=m.SqlAlchemyUserCreateAccess(), license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(), hasher=hasher, audit=v['audit'], receipts=receipts)

    def service(firsts=repo):
        return m.ManagedUserCreateService(**deps, results=firsts,
            replay_verifier=m.UserCreateReplayVerifier(source=firsts))

    password = b'Synthetic initial result'

    def command(name):
        return m.CreateManagedUser(v['tokens'][1], m.fixture.base.auth.CSRF,
            uuid4(), name, bytearray(password))

    first = service().create(command('Synthetic result healthy'), idempotency_key=str(uuid4()))
    uid = first.user_id
    tables = ('auth_users', 'auth_password_credentials', 'auth_sessions', 'auth_user_create_results',
              'auth_user_state_results', 'auth_password_change_results', 'auth_password_reset_results',
              'aud_events', 'plt_idempotency_receipts')

    def snapshot():
        return {table: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(
            sql.Identifier(table)))) for table in tables}

    def refused(call):
        try:
            call()
        except UserCreateReplayError as exc:
            assert str(exc) == 'AUTH_CREATE_REPLAY_UNAVAILABLE'
        else:
            raise AssertionError('Unavailable source accepted')

    before = snapshot()
    with v['uow']() as tx:
        original = repo.get(tx, user_id=uid)
        assert original is not None and original.first_view == first
        assert repo.get(tx, user_id=uuid4()) is None
        coordinates = dict(user_id=uid, credential_id=original.credential_id,
            actor_id=original.actor_id, audit_event_id=original.audit_event_id, trace_id=original.trace_id)
        for field in ('user_id', 'credential_id'):
            refused(lambda: repo.record(tx, **(coordinates | {field: uuid4()})))
        assert repo.verify_initial_password(tx, result=original, password=memoryview(password)) is True
        assert repo.verify_initial_password(tx, result=original,
            password=memoryview(password + b' wrong')) is False
    assert snapshot() == before

    class Verifier:
        def __init__(self, result=None, failure=None):
            self.result, self.failure, self.calls = result, failure, 0

        def verify_password(self, *args, **kwargs):
            self.calls += 1
            if self.failure is not None:
                raise self.failure
            return self.result

    no_verify = Verifier(failure=AssertionError('Unexpected verifier'))
    guarded = repo_type(verifier=no_verify)
    before = snapshot()
    with v['uow']() as tx:
        for bad in (replace(original, credential_id=uuid4()), replace(original, trace_id=uuid4())):
            refused(lambda: guarded.verify_initial_password(tx, result=bad,
                                                           password=memoryview(password)))
    assert no_verify.calls == 0 and snapshot() == before

    # Real get/original Credential query precedes these verifier Port faults.
    for verifier in (Verifier(result=None), Verifier(result=1), Verifier(result='yes'),
                     Verifier(failure=RuntimeError('Synthetic private verifier failure'))):
        faulty = repo_type(verifier=verifier)
        before = snapshot()
        with v['uow']() as tx:
            refused(lambda: faulty.verify_initial_password(tx, result=original,
                                                           password=memoryview(password)))
        assert verifier.calls == 1 and snapshot() == before

    # A real server-side division error aborts each independent caller transaction.
    for method in ('get', 'record', 'verify'):
        before = snapshot()
        with v['uow']() as tx:
            try:
                tx.session.execute(text('SELECT 1 / 0'))
            except DBAPIError as exc:
                assert exc.orig.sqlstate == '22012'
            else:
                raise AssertionError('SQL transaction did not abort')
            if method == 'get':
                refused(lambda: repo.get(tx, user_id=uid))
            elif method == 'record':
                refused(lambda: repo.record(tx, **coordinates))
            else:
                refused(lambda: repo.verify_initial_password(tx, result=original,
                                                             password=memoryview(password)))
        assert snapshot() == before

    marks = []

    class MissingAfterActualInsert(repo_type):
        def get(self, transaction, *, user_id):
            actual = super().get(transaction, user_id=user_id)
            assert actual is not None
            marks.append(actual.first_view.user_id)
            return None  # Explicit adapter return fault after real INSERT/get, not SQL mock.

    before = snapshot()
    failed_command = command('Synthetic result rollback')
    try:
        service(MissingAfterActualInsert(verifier=hasher)).create(
            failed_command, idempotency_key=str(uuid4()))
    except ManagedUserCreateError as exc:
        assert exc.code == 'AUTH_CREATE_UNAVAILABLE'
    else:
        raise AssertionError('Faulted result committed')
    assert len(marks) == 1 and snapshot() == before and not any(failed_command.password)
    healthy_command = command('Synthetic result rollback')
    recovered = service().create(healthy_command, idempotency_key=str(uuid4()))
    assert recovered.username_display == 'Synthetic result rollback' and not any(healthy_command.password)
    with v['uow']() as tx:
        assert repo.get(tx, user_id=recovered.user_id).first_view == recovered
    print('PASS actual PG create result: missing first/User/Credential, healthy true/false original password, two injected DTO mismatches, four verifier faults after real SQL, three actual SQL22012 aborted transactions fixed refusal; actual INSERT/read then injected None rolls back all nine tables/erases password; same name genuine creation recovers. Synthetic trust, no coverage/performance/production claim.')


if __name__ == '__main__':
    m.fixture.main(exercise=exercise)
