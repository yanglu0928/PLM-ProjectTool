"""Real isolated PG schema sources/immutability; not password change service."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import timedelta
from uuid import uuid4, UUID
import hashlib
import psycopg
from psycopg import sql
from sqlalchemy import inspect
from plm_assistant.modules.auth.infrastructure.user_orm import PasswordChangeResultRow
from plm_assistant.modules.auth.application.password_change_result import PasswordChangeResult

spec=spec_from_file_location('_change_schema_publication',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
f=module_from_spec(spec);spec.loader.exec_module(f)


def exercise(v):
    db=v['db'];a=f.a;cfg=a.create_migration_config(v['url']);table=PasswordChangeResultRow.__table__
    old=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'aud_events','plt_idempotency_receipts','job_jobs','job_outbox_events','doc_file_objects','prj_projects','lic_installations')
    def snap(include=True):return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t))))
        for t in old+((table.name,) if include else ())}
    before=snap(False)
    a.command.downgrade(cfg,'20260927_0047');assert snap(False)==before
    a.command.upgrade(cfg,'head');assert snap(False)==before
    assert db.execute('SELECT count(*) FROM plm.auth_password_change_results').fetchone()==(0,)
    with v['uow']() as tx:
        actual=inspect(tx.session.connection());columns=actual.get_columns(table.name,schema='plm')
        assert set(table.c.keys())=={c['name'] for c in columns} and all(not c['nullable'] for c in columns)
        for c in columns:assert isinstance(c['type'],type(table.c[c['name']].type))
        assert actual.get_pk_constraint(table.name,schema='plm')['constrained_columns']==['result_id']
        assert {c['name'] for c in actual.get_foreign_keys(table.name,schema='plm')}=={c.name for c in table.foreign_key_constraints}
        for kind,getter in (('UniqueConstraint',actual.get_unique_constraints),('CheckConstraint',actual.get_check_constraints)):
            assert {c['name'] for c in getter(table.name,schema='plm')}=={c.name for c in table.constraints if type(c).__name__==kind}
        assert next(c for c in columns if c['name']=='accepted_at')['default']=='statement_timestamp()'
    empty='auth_change_empty_'+uuid4().hex[:12]
    with f.base.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(empty)))
        try:
            ecfg=a.create_migration_config(v['url'].set(database=empty))
            a.command.upgrade(ecfg,'head');a.command.downgrade(ecfg,'20260927_0047');a.command.upgrade(ecfg,'head')
            with f.base.schema.connect(empty) as conn:assert conn.execute('SELECT count(*) FROM plm.auth_password_change_results').fetchone()==(0,)
        finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(empty)))
    # Explicit TEST_ONLY identity and credential sources; no password verification claim.
    user=f.base.auth.user(db,'Synthetic change schema user',b's'*32,'NONE')
    previous,oldid=db.execute('SELECT lock_version,active_password_credential_id FROM plm.auth_users WHERE user_id=%s',(user,)).fetchone()
    db.execute('''INSERT INTO plm.auth_sessions(user_id,credential_version,session_token_digest,csrf_digest,
        created_at,last_seen_at,idle_expires_at,absolute_expires_at) VALUES(%s,1,%s,%s,
        statement_timestamp()-interval '1 hour',statement_timestamp()-interval '1 hour',
        statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour')''',
        (user,hashlib.sha256(b'e'*32).digest(),hashlib.sha256(b'c'*32).digest()))
    new=db.execute('''INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,
        algorithm_id,parameter_set,must_change_password,changed_by)
        SELECT user_id,2,password_hash,algorithm_id,parameter_set,false,user_id
        FROM plm.auth_password_credentials WHERE password_credential_id=%s RETURNING password_credential_id''',(oldid,)).fetchone()[0]
    changed=db.execute('''UPDATE plm.auth_users SET active_password_credential_id=%s,credential_version=2,
        lock_version=lock_version+1,updated_by=user_id,updated_at=statement_timestamp()
        WHERE user_id=%s RETURNING updated_at''',(new,user)).fetchone()[0]
    trace=uuid4()
    with v['uow']() as tx:
        event=v['audit'].append(tx,f.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',target_project_id=None,
            actor_type='USER',actor_id=user,original_actor_id=None,actor_hint_digest=None,action='PASSWORD_CHANGED',
            outcome='SUCCESS',target_owner_module='auth',target_object_type='AUT-01',target_object_id=user,
            before_state='CREDENTIAL_V1',after_state='CREDENTIAL_V2'))
        tx.commit()
    value=dict(result_id=uuid4(),user_id=user,before_credential_id=oldid,credential_id=new,
        before_credential_version=1,credential_version=2,before_user_version=previous,user_version=previous+1,
        audit_event_id=event,trace_id=trace,revoked_session_count=2,changed_at=changed)
    def insert(data):
        names=tuple(data)
        db.execute(sql.SQL('INSERT INTO plm.auth_password_change_results({}) VALUES({})').format(
            sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),tuple(data.values()))
    def deny(data):
        before=snap()
        try:
            with db.transaction():insert(data)
        except psycopg.Error as exc:assert exc.sqlstate in ('P0001','23503','23514','23505','22003'),exc.sqlstate
        else:raise AssertionError('Invalid password result source accepted')
        assert snap()==before
    deny(value)
    db.execute("UPDATE plm.auth_sessions SET revoked_at=%s,revoke_reason='PASSWORD_CHANGED',lock_version=lock_version+1 WHERE user_id=%s AND revoked_at IS NULL",(changed,user))
    for bad in ({'result_id':UUID(int=0)},{'user_id':v['users'][1]},{'before_credential_id':new},
        {'before_credential_id':uuid4()},{'credential_id':oldid},{'credential_id':uuid4()},
        {'before_credential_version':0},{'before_credential_version':2},{'credential_version':3},
        {'before_user_version':previous+1},{'user_version':previous+2},{'trace_id':uuid4()},
        {'trace_id':UUID(int=0)},{'audit_event_id':uuid4()},{'revoked_session_count':0},
        {'revoked_session_count':1},{'revoked_session_count':3},{'changed_at':changed-timedelta(seconds=1)},
        {'accepted_at':'infinity'},{'accepted_at':changed-timedelta(seconds=1)},{'accepted_at':changed+timedelta(days=1)}):deny(value|bad)
    # Actual self/normal/current source refusal without mutating immutable credentials.
    for field,bad in (('state','DISABLED'),('updated_by',v['users'][1]),('lock_version',previous+2)):
        before=snap()
        try:
            with db.transaction():
                db.execute(sql.SQL('UPDATE plm.auth_users SET {}=%s WHERE user_id=%s').format(sql.Identifier(field)),(bad,user))
                insert(value)
        except psycopg.Error as exc:assert exc.sqlstate=='P0001'
        else:raise AssertionError('Wrong current User source accepted')
        assert snap()==before
    before=snap();required_insert_reached=False
    try:
        with db.transaction():insert(value);raise RuntimeError('Synthetic after actual first insert')
    except RuntimeError:pass
    assert snap()==before
    insert(value)
    accepted=db.execute('SELECT accepted_at FROM plm.auth_password_change_results WHERE result_id=%s',(value['result_id'],)).fetchone()[0]
    first=PasswordChangeResult(**(value|{'accepted_at':accepted}));assert first.public_data()=={'credential_version':2}
    deny(value|{'result_id':uuid4()})
    for override in ({'actor_id':v['users'][1]},{'action':'USER_NAME_CHANGED'},
        {'before_state':'CREDENTIAL_V0'},{'after_state':'CREDENTIAL_V3'},{'trace_id':uuid4()}):
        draft=dict(trace_id=trace,event_scope='DEPLOYMENT',target_project_id=None,actor_type='USER',actor_id=user,
            original_actor_id=None,actor_hint_digest=None,action='PASSWORD_CHANGED',outcome='SUCCESS',
            target_owner_module='auth',target_object_type='AUT-01',target_object_id=user,
            before_state='CREDENTIAL_V1',after_state='CREDENTIAL_V2')
        with v['uow']() as tx:
            wrong=v['audit'].append(tx,f.w.AuditEventDraft(**(draft|override)));tx.commit()
        deny(value|{'result_id':uuid4(),'audit_event_id':wrong})
    # Isolate must-change=true denial with every other source, including real count1, consistent.
    before=snap()
    try:
        with db.transaction():
            db.execute('''INSERT INTO plm.auth_sessions(user_id,credential_version,session_token_digest,csrf_digest,
                absolute_expires_at,idle_expires_at) VALUES(%s,2,%s,%s,statement_timestamp()+interval '8 hours',
                statement_timestamp()+interval '30 minutes')''',(user,hashlib.sha256(b't'*32).digest(),hashlib.sha256(b'c'*32).digest()))
            required=db.execute('''INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,
                algorithm_id,parameter_set,must_change_password,changed_by)
                SELECT user_id,3,password_hash,algorithm_id,parameter_set,true,user_id
                FROM plm.auth_password_credentials WHERE password_credential_id=%s RETURNING password_credential_id''',(new,)).fetchone()[0]
            at=db.execute('''UPDATE plm.auth_users SET active_password_credential_id=%s,credential_version=3,
                lock_version=lock_version+1,updated_by=user_id,updated_at=statement_timestamp()
                WHERE user_id=%s RETURNING updated_at''',(required,user)).fetchone()[0]
            db.execute("UPDATE plm.auth_sessions SET revoked_at=%s,revoke_reason='PASSWORD_CHANGED',lock_version=lock_version+1 WHERE user_id=%s AND revoked_at IS NULL",(at,user))
            badtrace=uuid4()
            # Direct SQL Audit is a schema fixture; app transaction uses the Audit Port elsewhere.
            bad_event=db.execute('''INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,
                target_owner_module,target_object_type,target_object_id,before_state,after_state)
                VALUES(%s,'DEPLOYMENT','USER',%s,'PASSWORD_CHANGED','SUCCESS','auth','AUT-01',%s,
                'CREDENTIAL_V2','CREDENTIAL_V3') RETURNING audit_event_id''',(badtrace,user,user)).fetchone()[0]
            required_insert_reached=True
            insert(value|{'result_id':uuid4(),'before_credential_id':new,'credential_id':required,
                'before_credential_version':2,'credential_version':3,'before_user_version':previous+1,
                'user_version':previous+2,'changed_at':at,'revoked_session_count':1,'audit_event_id':bad_event,'trace_id':badtrace})
    except psycopg.Error as exc:assert exc.sqlstate=='P0001' and required_insert_reached,exc.sqlstate
    else:raise AssertionError('Must-change after credential accepted as normal password change')
    assert snap()==before
    history=tuple(db.execute('SELECT * FROM plm.auth_password_change_results ORDER BY result_id'))
    db.execute("UPDATE plm.auth_users SET username_display='Later synthetic name',lock_version=lock_version+1,updated_at=statement_timestamp() WHERE user_id=%s",(user,))
    assert tuple(db.execute('SELECT * FROM plm.auth_password_change_results ORDER BY result_id'))==history
    for query in ('UPDATE plm.auth_password_change_results SET trace_id=trace_id','DELETE FROM plm.auth_password_change_results',
        'TRUNCATE plm.auth_password_change_results'):
        before=snap()
        try:
            with db.transaction():db.execute(query)
        except psycopg.Error as exc:assert exc.sqlstate=='P0001'
        else:raise AssertionError('First history mutated')
        assert snap()==before
    before=snap()
    try:a.command.downgrade(cfg,'20260927_0047')
    except Exception as exc:assert getattr(getattr(exc,'orig',None),'sqlstate',None)=='P0001'
    else:raise AssertionError('Nonempty password history dropped')
    assert snap()==before and db.execute('SELECT version_num FROM plm.alembic_version').fetchone()==('20260927_0048',)
    print('PASS password change schema: real empty/populated0047-48 roundtrip preserves twelve old tables/no backfill; ORM parity; exact before/after Credential/User/self Audit/time/source and revoked count2 including expired/unrevoked refuses, invalid inputs rollback, actual insert-fault rollback, later User history immutable, update/delete/truncate and nonempty downgrade refuse head48. TEST_ONLY source, NOT real password/current-CSRF/atomic change/replay/HTTP/package proof.')


if __name__=='__main__':f.main(exercise=exercise)
