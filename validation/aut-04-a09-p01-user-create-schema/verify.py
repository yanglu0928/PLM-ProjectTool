"""Actual PostgreSQL schema evidence, not authorized User-create/replay proof."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import UUID, uuid4
from datetime import timedelta
from psycopg import sql
import psycopg
from sqlalchemy import inspect
from plm_assistant.modules.auth.infrastructure.user_orm import UserCreateResultRow
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_create_result import UserCreateResult

spec = spec_from_file_location('_user_create_schema_publication', Path(__file__).resolve().parents[1]
    / 'aud-03-a06-a04-p03-a04-p03-publication' / 'verify.py')
fixture = module_from_spec(spec); spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db']; a=fixture.a; config=a.create_migration_config(v['url'])
    table=UserCreateResultRow.__table__
    old=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts',
         'job_jobs','job_outbox_events','doc_file_objects','prj_projects','lic_installations')
    def snapshot(include=True):
        names=old+((table.name,) if include else ())
        return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in names}
    before=snapshot(False)
    a.command.downgrade(config,'20260927_0045'); assert snapshot(False)==before
    a.command.upgrade(config,'head'); assert snapshot(False)==before
    assert db.execute('SELECT count(*) FROM plm.auth_user_create_results').fetchone()==(0,)
    with v['uow']() as tx:
        actual=inspect(tx.session.connection())
        columns=actual.get_columns(table.name,schema='plm')
        assert {c['name'] for c in columns}==set(table.c.keys())
        assert all(not c['nullable'] for c in columns)
        assert {f['name'] for f in actual.get_foreign_keys(table.name,schema='plm')} == {
            f.name for f in table.foreign_key_constraints}
        assert {c['name'] for c in actual.get_check_constraints(table.name,schema='plm')} == {
            c.name for c in table.constraints if c.__class__.__name__=='CheckConstraint'}
        assert {c['name'] for c in actual.get_unique_constraints(table.name,schema='plm')} == {
            c.name for c in table.constraints if c.__class__.__name__=='UniqueConstraint'}
    empty='auth_create_empty_'+uuid4().hex[:12]
    with fixture.base.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(empty)))
        try:
            cfg=a.create_migration_config(v['url'].set(database=empty))
            a.command.upgrade(cfg,'head');a.command.downgrade(cfg,'20260927_0045');a.command.upgrade(cfg,'head')
            with fixture.base.schema.connect(empty) as conn:
                assert conn.execute('SELECT count(*) FROM plm.auth_user_create_results').fetchone()==(0,)
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(empty)))
    repo=SqlAlchemyUserRepository(); actor=v['users'][1]; trace=uuid4()
    # Real owned User/Credential activation and Audit Port, explicitly TEST_ONLY hash.
    # P01 proves schema coordinates, not Scrypt or production authorization.
    with v['uow']() as tx:
        user=repo.add_user(tx,username_display='Synthetic first creation',
            username_normalized='synthetic first creation',actor_id=actor)
        credential=repo.add_credential(tx,user_id=user,actor_id=actor,
            password_hash=PasswordHashResult('SCHEMA_TEST_ONLY','TEST_ONLY',{}))
        assert repo.activate_initial_credential(tx,user_id=user,credential_id=credential,actor_id=actor)
        event=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',
            target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
            action='USER_CREATED',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
            target_object_id=user,after_state='ENABLED'))
        tx.commit()
    source=db.execute('SELECT username_display,created_at,updated_at FROM plm.auth_users WHERE user_id=%s',(user,)).fetchone()
    values=dict(user_id=user,credential_id=credential,actor_id=actor,audit_event_id=event,trace_id=trace,
        username_display=source[0],account_state='ENABLED',deployment_role='NONE',credential_version=1,
        lock_version=1,created_at=source[1],updated_at=source[2])
    def insert(values):
        names=tuple(values)
        db.execute(sql.SQL('INSERT INTO plm.auth_user_create_results({}) VALUES({})').format(
            sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),
            tuple(values.values()))
    def deny_insert(change):
        before=snapshot()
        try:
            with db.transaction(): insert(values|change)
        except psycopg.Error: pass
        else: raise AssertionError('Invalid User first source accepted')
        assert snapshot()==before
    for change in ({'user_id':uuid4()},{'credential_id':uuid4()},{'actor_id':v['users'][0]},
        {'actor_id':user},{'trace_id':uuid4()},{'trace_id':UUID(int=0)},{'audit_event_id':uuid4()},
        {'username_display':'Changed snapshot'},{'account_state':'DISABLED'},
        {'deployment_role':'DEPLOYMENT_ADMIN'},{'credential_version':2},{'lock_version':0},
        {'created_at':source[1]-timedelta(seconds=1)}, {'updated_at':source[2]+timedelta(seconds=1)},
        {'accepted_at':'1900-01-01'}, {'accepted_at':'infinity'}):
        deny_insert(change)
    # Valid Audit shape but different target/action/trace must not be a creation source.
    with v['uow']() as tx:
        wrong=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',
            target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
            action='USER_READ',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
            target_object_id=user,after_state='ENABLED'))
        tx.commit()
    deny_insert({'audit_event_id':wrong})
    # Actual current target source mismatch, restore only this synthetic fixture afterward.
    for column,value,restore in (('state','DISABLED','ENABLED'),('deployment_role','DEPLOYMENT_ADMIN','NONE'),
        ('lock_version',2,1),('created_by',v['users'][0],actor),('updated_by',v['users'][0],actor)):
        db.execute(sql.SQL('UPDATE plm.auth_users SET {}=%s WHERE user_id=%s').format(sql.Identifier(column)),(value,user))
        try:deny_insert({})
        finally:
            db.execute(sql.SQL('UPDATE plm.auth_users SET {}=%s WHERE user_id=%s').format(sql.Identifier(column)),(restore,user))
    before=snapshot()
    try:
        with db.transaction():
            insert(values)
            raise RuntimeError('Synthetic after real first-result insertion')
    except RuntimeError: pass
    assert snapshot()==before
    insert(values)
    accepted=db.execute('SELECT accepted_at FROM plm.auth_user_create_results WHERE user_id=%s',(user,)).fetchone()[0]
    result=UserCreateResult(UserReadView(user,source[0],'ENABLED','NONE',1,source[1],source[2],1),
        credential,actor,event,trace,accepted)
    assert result.first_view.lock_version==1
    deny_insert({})
    for statement in ('UPDATE plm.auth_user_create_results SET username_display=\'Changed\'',
                      'DELETE FROM plm.auth_user_create_results','TRUNCATE plm.auth_user_create_results'):
        before=snapshot()
        try:
            with db.transaction(): db.execute(statement)
        except psycopg.Error as exc: assert exc.sqlstate=='P0001'
        else: raise AssertionError('First result history mutated')
        assert snapshot()==before
    first=tuple(db.execute('SELECT * FROM plm.auth_user_create_results'))
    db.execute("UPDATE plm.auth_users SET state='DISABLED',username_display='Synthetic renamed',"
        "lock_version=2,updated_at=statement_timestamp() WHERE user_id=%s",(user,))
    assert tuple(db.execute('SELECT * FROM plm.auth_user_create_results'))==first
    before=snapshot()
    try:a.command.downgrade(config,'20260927_0045')
    except Exception as exc: assert getattr(getattr(exc,'orig',None),'sqlstate',None)=='P0001'
    else:raise AssertionError('User first history discarded')
    assert snapshot()==before
    assert db.execute('SELECT version_num FROM plm.alembic_version').fetchone()==('20260927_0046',)
    print('User first schema PASS: actual empty/populated up-down-re-up, ten old tables preserved/no backfill, '
        'ORM columns/FK/check/unique parity, real owned initial User/Credential/Audit source, invalid source/shape/time '
        'refused without writes, insert-fault rollback, immutable UPDATE/DELETE/TRUNCATE, later disable/rename '
        'preserves original safe snapshot, populated down refuses at0046. TEST_ONLY credential is explicitly '
        'schema fixture, NOT real Scrypt/replay/current Admin-CSRF/receipt/HTTP/production/Gate/package proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
