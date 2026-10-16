"""Actual current SQL projection and explicitly injected fact/Port failures."""
from dataclasses import replace
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from psycopg.errors import UniqueViolation
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.auth.infrastructure.session_credential import SqlAlchemySessionCredentialFacts
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_projection_atomic', ROOT / 'validation' /
                              'aut-04-a12-p05-a05-reset-atomic' / 'verify.py')
r = module_from_spec(spec)
spec.loader.exec_module(r)
m = r.m


def exercise(v):
    db, uid, token = v['db'], v['users'][0], v['tokens'][0]
    tables = ('auth_users', 'auth_password_credentials', 'auth_sessions', 'auth_user_create_results',
              'auth_user_state_results', 'auth_password_change_results', 'auth_password_reset_results',
              'aud_events', 'plt_idempotency_receipts', 'prj_projects', 'prj_departments',
              'prj_project_members')

    def snapshot():
        return {table: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(
            sql.Identifier(table)))) for table in tables}

    class Projects:
        def __init__(self, result=None, failure=None):
            self.result, self.failure, self.calls = result, failure, 0

        def for_user(self, transaction, user_id):
            self.calls += 1
            if self.failure is not None:
                raise self.failure
            return self.result

    real = SqlAlchemyAuthorizedProjects()
    view = SqlAlchemySessionView(unit_of_work=v['uow'], projects=real)
    before = snapshot()
    healthy = view.resolve_for_session(user_id=uid, session_token=token)
    assert healthy.password_change_required is False
    assert len(healthy.authorized_projects) == 1
    assert healthy.authorized_projects[0].project_id == v['project']
    assert view.resolve(uid) == healthy and snapshot() == before

    def denied(call, error, message=None):
        before = snapshot()
        try:
            call()
        except error as exc:
            if message is not None:
                assert str(exc) == message
        else:
            raise AssertionError('Projection unexpectedly accepted')
        assert snapshot() == before, 'Projection changed twelve business tables'

    no_projects = Projects(failure=AssertionError('Project must not be read'))
    guarded = SqlAlchemySessionView(unit_of_work=v['uow'], projects=no_projects)
    for target, proof in ((uid, b'x' * 32), (uuid4(), token)):
        denied(lambda: guarded.resolve_for_session(user_id=target, session_token=proof),
               LookupError, 'Current Session unavailable')
    denied(lambda: guarded.resolve(uuid4()), LookupError, 'Current credential unavailable')
    assert no_projects.calls == 0

    # Actual current SQL is not mocked. Deliberately inconsistent DTO inputs only.
    before = snapshot()
    with v['uow']() as tx:
        fact = SqlAlchemySessionCredentialFacts().get(tx, session_token=token,
                                                     now=datetime.now(timezone.utc))
        assert fact is not None and fact.user_id == uid
        for bad in (replace(fact, credential_version=fact.credential_version + 1),
                    replace(fact, credential_id=uuid4()),
                    replace(fact, password_change_required=not fact.password_change_required)):
            try:
                guarded._resolve(tx, uid, bad)
            except LookupError as exc:
                assert str(exc) == 'Current credential binding unavailable'
            else:
                raise AssertionError('Mismatched current fact accepted')
    assert snapshot() == before and no_projects.calls == 0

    for source in (Projects(result=[]), Projects(result=(object(),)),
                   Projects(failure=RuntimeError('Synthetic Project source failure'))):
        faulty = SqlAlchemySessionView(unit_of_work=v['uow'], projects=source)
        denied(lambda: faulty.resolve_for_session(user_id=uid, session_token=token), RuntimeError)
        assert source.calls == 1
    assert view.resolve_for_session(user_id=uid, session_token=token) == healthy

    # Genuine Service-generated must-change Credential, not a patched SQL flag.
    hasher, receipts = m.ScryptPasswordHasher(), m.SqlAlchemyIdempotencyReceipts()
    firsts = m.SqlAlchemyUserCreateResultRepository(verifier=hasher)
    creator = m.ManagedUserCreateService(unit_of_work=v['uow'], access=m.SqlAlchemyUserCreateAccess(),
        license_guard=v['guard'], users=m.SqlAlchemyUserRepository(), results=firsts,
        replay_verifier=m.UserCreateReplayVerifier(source=firsts), hasher=hasher,
        audit=v['audit'], receipts=receipts)
    created = creator.create(m.CreateManagedUser(v['tokens'][1], m.fixture.base.auth.CSRF, uuid4(),
        'Synthetic projection restricted', bytearray(b'Synthetic projection original')),
        idempotency_key=str(uuid4()))
    results = r.SqlAlchemyPasswordResetResults(verifier=hasher)
    reset = r.PasswordResetService(unit_of_work=v['uow'], access=r.SqlAlchemyPasswordResetAccess(verifier=hasher),
        repository=r.SqlAlchemyPasswordResetRepository(), results=results,
        replay_verifier=r.PasswordResetReplayVerifier(source=results), hasher=hasher,
        audit=v['audit'], receipts=receipts, license_guard=v['guard'])
    expected = db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s',
                          (created.user_id,)).fetchone()[0]
    reset.reset(r.ResetPassword(v['tokens'][1], m.fixture.base.auth.CSRF, uuid4(), created.user_id,
        expected, True, r.PasswordResetProof(bytearray(b'Synthetic projection temporary'))),
        idempotency_key=str(uuid4()))
    sessions = m.SessionService(unit_of_work=v['uow'], repository=m.SqlAlchemySessionRepository(),
        issue_access=m.SqlAlchemyPasswordIssueAccess(hasher), audit=v['audit'], idempotency=receipts)
    restricted = sessions.issue(user_id=created.user_id, trace_id=uuid4(),
        proof=m.PasswordIssueProof(bytearray(b'Synthetic projection temporary')))
    before = snapshot()
    projected = guarded.resolve_for_session(user_id=created.user_id, session_token=restricted.token)
    assert projected.public_data()['authorized_projects'] == []
    assert projected.public_data()['deployment_role'] == 'NONE'
    assert projected.password_change_required is True
    assert no_projects.calls == 0 and snapshot() == before

    # Actual Schema forbids duplicate live membership; do not disable its constraint.
    schema = m.fixture.base.schema
    project = schema.insert(db, 'prj_projects', dict(project_code='PROJECTION',
        project_code_normalized='projection', name='Synthetic projection', created_by=uid), 'project_id')
    department = schema.insert(db, 'prj_departments', dict(project_id=project,
        department_code='PROJECTION', department_code_normalized='projection',
        name='Synthetic projection'), 'department_id')
    before = snapshot()
    try:
        schema.insert(db, 'prj_project_members', dict(project_id=project, user_id=uid,
            department_id=department, project_role='PROJECT_MANAGER'), 'project_member_id')
    except UniqueViolation as exc:
        assert exc.diag.constraint_name == 'uq_prj_members__user_active'
    else:
        raise AssertionError('Second active membership inserted')
    assert snapshot() == before
    assert view.resolve_for_session(user_id=uid, session_token=token) == healthy
    assert snapshot() == before
    print('PASS actual PG Session projection: current healthy; missing Session/user; three injected fact mismatches against real SQL; three injected Project Port failures; actual reset restricted/no Project; actual duplicate membership blocked by unique constraint, original projection preserved. Twelve tables read-only per projection. Project ambiguity branch not reached, synthetic trust, no production/coverage/performance claim.')


if __name__ == '__main__':
    m.fixture.main(exercise=exercise)
