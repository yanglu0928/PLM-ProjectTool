"""Actual minimal member-name projection, typed-input behavior and owned rollback."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.auth.infrastructure.project_member_names import SqlAlchemyProjectMemberNames

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('_member_names_publication', ROOT / 'validation' /
                              'aud-03-a06-a04-p03-a04-p03-publication/verify.py')
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def exercise(v):
    db = v['db']
    uid, other = v['users']
    source = SqlAlchemyProjectMemberNames()
    names = dict(db.execute('SELECT user_id,username_display FROM plm.auth_users WHERE user_id=ANY(%s)',
                            ([uid,other],)).fetchall())
    assert set(names) == {uid,other}
    tables = ('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results',
              'auth_user_state_results','auth_password_change_results','auth_password_reset_results',
              'aud_events','plt_idempotency_receipts')
    def snapshot():
        return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def read(ids, expected):
        before = snapshot()
        with v['uow']() as tx:
            assert source.display_names(tx,ids) == expected
        assert snapshot() == before
    for ids, expected in (((),{}),((uid,),{uid:names[uid]}),((uid,other),names),
                          ((uid,uid,uuid4()),{uid:names[uid]}),((uuid4(),),{}),
                          ((None,),{}),((str(uid),),{uid:names[uid]})):
        read(ids,expected)
    before = snapshot()
    with v['uow']() as tx:
        tx.session.execute(text("UPDATE plm.auth_users SET username_display='Synthetic current member name',"
            "username_normalized='synthetic current member name',state='DISABLED',lock_version=lock_version+1 WHERE user_id=:uid"),{'uid':uid})
        assert source.display_names(tx,(uid,other)) == (names | {uid:'Synthetic current member name'})
    assert snapshot() == before
    for case in ('invalid_uuid','aborted_transaction'):
        before = snapshot()
        with v['uow']() as tx:
            if case == 'aborted_transaction':
                try:
                    tx.session.execute(text('SELECT 1/0'))
                except DBAPIError as exc:
                    assert exc.orig.sqlstate == '22012'
                else:
                    raise AssertionError('Actual SQL fault missing')
            try:
                source.display_names(tx,('Synthetic not UUID',) if case == 'invalid_uuid' else (uid,))
            except DBAPIError as exc:
                assert exc.orig.sqlstate == ('22P02' if case == 'invalid_uuid' else '25P02')
            else:
                raise AssertionError('Actual invalid SQL source accepted')
        assert snapshot() == before
        read((uid,other),names)
        print('MEMBER_NAME_SOURCE_RESULT ' + case + ' PASS actual SQL / nine-table rollback / healthy reread')
    print('PASS: seven actual projections, current renamed disabled User, two SQL failures; None absent and valid UUID string coerced by PG, not a permission/validation claim.')


if __name__ == '__main__':
    fixture.main(exercise=exercise)
