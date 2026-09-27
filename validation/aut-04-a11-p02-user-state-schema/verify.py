"""Actual PG source/immutability/migration evidence, not authorized state commands."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import UUID,uuid4
from datetime import timedelta
import hashlib
import psycopg
from psycopg import sql
from sqlalchemy import inspect,text
from plm_assistant.modules.auth.infrastructure.user_orm import UserStateResultRow
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.application.user_state_result import UserStateResult

spec=spec_from_file_location('_state_schema_publication',Path(__file__).resolve().parents[1]
    /'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];a=fixture.a;config=a.create_migration_config(v['url']);table=UserStateResultRow.__table__
    old=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','aud_events',
        'plt_idempotency_receipts','job_jobs','job_outbox_events','doc_file_objects','prj_projects','lic_installations')
    def snap(include=True):
        return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t))))
            for t in old+((table.name,) if include else ())}
    before=snap(False)
    a.command.downgrade(config,'20260927_0046');assert snap(False)==before
    a.command.upgrade(config,'head');assert snap(False)==before
    assert db.execute('SELECT count(*) FROM plm.auth_user_state_results').fetchone()==(0,)
    with v['uow']() as tx:
        actual=inspect(tx.session.connection());columns=actual.get_columns(table.name,schema='plm')
        assert {c['name'] for c in columns}==set(table.c.keys()) and all(not c['nullable'] for c in columns)
        for c in columns:assert isinstance(c['type'],type(table.c[c['name']].type)),c['name']
        assert actual.get_pk_constraint(table.name,schema='plm')['constrained_columns']==['result_id']
        assert {c['name'] for c in actual.get_foreign_keys(table.name,schema='plm')}=={c.name for c in table.foreign_key_constraints}
        for kind,getter in (('CheckConstraint',actual.get_check_constraints),('UniqueConstraint',actual.get_unique_constraints)):
            assert {c['name'] for c in getter(table.name,schema='plm')}=={c.name for c in table.constraints if type(c).__name__==kind}
        assert next(c for c in columns if c['name']=='accepted_at')['default']=='statement_timestamp()'
    empty='auth_state_empty_'+uuid4().hex[:12]
    with fixture.base.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(empty)))
        try:
            cfg=a.create_migration_config(v['url'].set(database=empty))
            a.command.upgrade(cfg,'head');a.command.downgrade(cfg,'20260927_0046');a.command.upgrade(cfg,'head')
            with fixture.base.schema.connect(empty) as conn:
                assert conn.execute('SELECT count(*) FROM plm.auth_user_state_results').fetchone()==(0,)
        finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(empty)))
    actor=v['users'][1];trace=uuid4()
    # Owned schema-only identity/Credential/Session fixture; not real authentication.
    user=fixture.base.auth.user(db,'Synthetic state schema user',b's'*32,'NONE')
    # An additional expired but not revoked Session must also be revoked.
    db.execute("""INSERT INTO plm.auth_sessions(user_id,credential_version,session_token_digest,csrf_digest,
        created_at,last_seen_at,idle_expires_at,absolute_expires_at)
        VALUES(%s,1,%s,%s,statement_timestamp()-interval '1 hour',statement_timestamp()-interval '1 hour',
          statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour')""",
        (user,hashlib.sha256(b'e'*32).digest(),hashlib.sha256(b'c'*32).digest()))
    assert db.execute('SELECT count(*) FROM plm.auth_sessions WHERE user_id=%s AND revoked_at IS NULL',(user,)).fetchone()==(2,)
    with v['uow']() as tx:
        previous=tx.session.execute(text('SELECT lock_version FROM plm.auth_users WHERE user_id=:user FOR UPDATE'),dict(user=user)).scalar_one()
        updated=tx.session.execute(text("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1,"
            "updated_by=:actor,updated_at=statement_timestamp() WHERE user_id=:user RETURNING updated_at"),
            dict(user=user,actor=actor)).scalar_one()
        # Schema does not itself execute revocation; first prove it rejects the unrevoked source.
        event=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',
            target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
            action='USER_DISABLED',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
            target_object_id=user,before_state='ENABLED',after_state='DISABLED'))
        tx.commit()
    def values(operation,expected,event,trace,count):
        row=db.execute('SELECT username_display,state,deployment_role,credential_version,lock_version,created_at,updated_at '
            'FROM plm.auth_users WHERE user_id=%s',(user,)).fetchone()
        return dict(result_id=uuid4(),user_id=user,actor_id=actor,audit_event_id=event,trace_id=trace,
            operation=operation,expected_version=expected,revoked_session_count=count,
            **dict(zip(('username_display','account_state','deployment_role','credential_version','lock_version','created_at','updated_at'),row)))
    disabled=values('DISABLE',previous,event,trace,2)
    def insert(value):
        names=tuple(value)
        db.execute(sql.SQL('INSERT INTO plm.auth_user_state_results({}) VALUES({})').format(
            sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),tuple(value.values()))
    def deny(value):
        before=snap()
        try:
            with db.transaction():insert(value)
        except psycopg.Error as exc:assert exc.sqlstate in ('P0001','23503','23514','23505','22003'),exc.sqlstate
        else:raise AssertionError('Invalid state first/source accepted')
        assert snap()==before
    deny(disabled)
    db.execute("UPDATE plm.auth_sessions SET revoked_at=%s,revoke_reason='USER_DISABLED',lock_version=lock_version+1 "
        "WHERE user_id=%s AND revoked_at IS NULL",(updated,user))
    for change in ({'result_id':UUID(int=0)},{'user_id':uuid4()},{'actor_id':v['users'][0]},
        {'trace_id':uuid4()},{'trace_id':UUID(int=0)},{'audit_event_id':uuid4()},
        {'username_display':'Wrong first name'},{'operation':'ENABLE'},{'account_state':'ENABLED'},
        {'deployment_role':'DEPLOYMENT_ADMIN'},{'credential_version':0},{'credential_version':2},
        {'expected_version':previous+1},{'lock_version':disabled['lock_version']+1},
        {'revoked_session_count':0},{'revoked_session_count':1},{'revoked_session_count':3},
        {'revoked_session_count':-1},{'created_at':disabled['created_at']-timedelta(seconds=1)},
        {'updated_at':updated+timedelta(seconds=1)},{'accepted_at':'1900-01-01'},{'accepted_at':'infinity'},
        {'accepted_at':updated+timedelta(days=1)}):
        deny(disabled|change)
    before=snap()
    try:
        with db.transaction():insert(disabled);raise RuntimeError('Synthetic after real snapshot insert')
    except RuntimeError:pass
    assert snap()==before
    insert(disabled)
    accepted=db.execute('SELECT accepted_at FROM plm.auth_user_state_results WHERE result_id=%s',
        (disabled['result_id'],)).fetchone()[0]
    first=UserStateResult(disabled['result_id'],UserReadView(user,disabled['username_display'],'DISABLED','NONE',
        disabled['credential_version'],disabled['created_at'],updated,disabled['lock_version']),
        actor,event,trace,'DISABLE',previous,2,accepted)
    assert first.first_view.account_state=='DISABLED' and first.revoked_session_count==2
    deny(disabled|{'result_id':uuid4()})
    history=tuple(db.execute('SELECT * FROM plm.auth_user_state_results ORDER BY result_id'))
    # Real same-UOW synthetic re-enable + Audit source, no Session revival.
    trace2=uuid4()
    with v['uow']() as tx:
        tx.session.execute(text("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1,"
            "updated_by=:actor,updated_at=statement_timestamp() WHERE user_id=:user"),dict(user=user,actor=actor))
        event2=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=trace2,event_scope='DEPLOYMENT',
            target_project_id=None,actor_type='USER',actor_id=actor,original_actor_id=None,actor_hint_digest=None,
            action='USER_ENABLED',outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',
            target_object_id=user,before_state='DISABLED',after_state='ENABLED'))
        tx.commit()
    assert tuple(db.execute('SELECT * FROM plm.auth_user_state_results ORDER BY result_id'))==history
    assert db.execute('SELECT count(*) FROM plm.auth_sessions WHERE user_id=%s AND revoked_at IS NULL',(user,)).fetchone()==(0,)
    enabled=values('ENABLE',disabled['lock_version'],event2,trace2,0)
    deny(enabled|{'revoked_session_count':1});deny(enabled|{'audit_event_id':event})
    insert(enabled)
    # Later metadata does not alter either original state response.
    history=tuple(db.execute('SELECT * FROM plm.auth_user_state_results ORDER BY result_id'))
    db.execute("UPDATE plm.auth_users SET username_display='Synthetic state later name',lock_version=lock_version+1 "
        "WHERE user_id=%s",(user,))
    assert tuple(db.execute('SELECT * FROM plm.auth_user_state_results ORDER BY result_id'))==history
    for statement in ('UPDATE plm.auth_user_state_results SET revoked_session_count=0',
        'DELETE FROM plm.auth_user_state_results','TRUNCATE plm.auth_user_state_results'):
        before=snap()
        try:
            with db.transaction():db.execute(statement)
        except psycopg.Error as exc:assert exc.sqlstate=='P0001'
        else:raise AssertionError('State history changed')
        assert snap()==before
    before=snap()
    try:a.command.downgrade(config,'20260927_0046')
    except Exception as exc:assert getattr(getattr(exc,'orig',None),'sqlstate',None)=='P0001'
    else:raise AssertionError('State history discarded')
    assert snap()==before and db.execute('SELECT version_num FROM plm.alembic_version').fetchone()==('20260927_0049',)
    print('PASS state first schema: actual empty/populated up-down-up, eleven old tables preserved/no backfill, '
        'ORM columns/types/nullable/PK/FK/check/unique/default parity, precise User/Credential/Audit/time source, '
        'unrevoked Session rejection and exact two revoked including expired source/count, insert-fault rollback, '
        'enable source zero count/no revival, immutable original views after later state/name, UPDATE/DELETE/TRUNCATE '
        'and populated downgrade refusal. TEST_ONLY auth fixtures, not command/current permission/replay/self-disable/'
        'lastAdmin/HTTP/production/performance/Gate/package proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
