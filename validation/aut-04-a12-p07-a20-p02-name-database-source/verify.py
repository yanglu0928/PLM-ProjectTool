"""Actual PostgreSQL name repository refusal and rollback; no successful SQL mocks."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from plm_assistant.modules.auth.application.user_name_patch import UserNamePatchError
from plm_assistant.modules.auth.domain.username import normalize_username
from plm_assistant.modules.auth.infrastructure.user_name_patch_repository import SqlAlchemyUserNamePatchRepository

spec = spec_from_file_location('_name_source_base', Path(__file__).resolve().parents[1]
    / 'aut-04-a10-p01-user-name-patch' / 'verify.py')
base = module_from_spec(spec)
spec.loader.exec_module(base)


def exercise(v):
    base.exercise(v)
    db = v['db']
    uid = base.fixture.base.auth.user(db, 'Synthetic name source boundary', b'n' * 32, 'NONE')
    reserved = base.fixture.base.auth.user(db, 'Synthetic name source reserved', b'r' * 32, 'NONE')
    assert reserved != uid
    version = db.execute('SELECT lock_version FROM plm.auth_users WHERE user_id=%s', (uid,)).fetchone()[0]
    tables = ('auth_users', 'auth_password_credentials', 'auth_sessions', 'auth_user_create_results',
              'auth_user_state_results', 'auth_password_change_results', 'auth_password_reset_results',
              'aud_events', 'plt_idempotency_receipts')
    def snapshot():
        return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t))))
                for t in tables}
    repo = SqlAlchemyUserNamePatchRepository()
    cases = ('missing', 'source', 'maximum', 'duplicate', 'other_integrity', 'time_backwards')
    for case in cases:
        before = snapshot()
        with v['uow']() as tx:
            target, expected, actor = uid, version, v['users'][1]
            name = normalize_username('Synthetic actual name update')
            if case == 'missing': target = uuid4()
            if case == 'source':
                tx.session.execute(text("UPDATE plm.auth_users SET username_normalized='synthetic wrong source' WHERE user_id=:uid"), {'uid': uid})
            if case == 'maximum':
                expected = 9223372036854775807
                tx.session.execute(text('UPDATE plm.auth_users SET lock_version=:version WHERE user_id=:uid'),
                                   {'uid': uid, 'version': expected})
            if case == 'duplicate': name = normalize_username('SYNTHETIC NAME SOURCE RESERVED')
            if case == 'other_integrity':
                # TEST_ONLY additive DDL in this uncommitted owned-fixture UOW.
                tx.session.execute(text("ALTER TABLE plm.auth_users ADD CONSTRAINT ck_test_name_source_refusal CHECK (username_display <> 'Synthetic actual name update')"))
            if case == 'time_backwards':
                tx.session.execute(text("UPDATE plm.auth_users SET updated_at=statement_timestamp()+interval '1 day' WHERE user_id=:uid"), {'uid': uid})
            try:
                repo.patch(tx, user_id=target, expected_version=expected, username=name, actor_id=actor)
            except UserNamePatchError as exc:
                assert case != 'other_integrity'
                assert exc.code == {'missing': 'RESOURCE_NOT_FOUND', 'source': 'AUTH_PATCH_UNAVAILABLE',
                    'maximum': 'CONFLICT_VERSION', 'duplicate': 'CONFLICT_DUPLICATE',
                    'time_backwards': 'AUTH_PATCH_UNAVAILABLE'}[case]
            except IntegrityError as exc:
                assert case == 'other_integrity' and exc.orig.sqlstate == '23514'
                assert exc.orig.diag.constraint_name == 'ck_test_name_source_refusal'
            else:
                raise AssertionError('Actual unsafe name update accepted: ' + case)
        assert snapshot() == before, case
        assert db.execute("SELECT count(*) FROM pg_constraint WHERE conname='ck_test_name_source_refusal'").fetchone() == (0,)
        print('NAME_SOURCE_RESULT ' + case + ' PASS actual PostgreSQL / nine-table rollback')
    print('PASS: six actual name-source refusals and original name/publication regression; synthetic owned fixture only.')


if __name__ == '__main__':
    base.fixture.main(exercise=exercise)
