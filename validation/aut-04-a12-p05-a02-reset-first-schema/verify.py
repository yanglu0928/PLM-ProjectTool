"""Real isolated PG reset source/migration; TEST_ONLY credentials, no reset service claim."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import timedelta
from uuid import uuid4,UUID
from concurrent.futures import ThreadPoolExecutor
import psycopg
from psycopg import sql
from sqlalchemy import inspect
from plm_assistant.modules.auth.infrastructure.user_orm import PasswordResetResultRow
from plm_assistant.modules.auth.application.password_reset_result import PasswordResetResult

spec=spec_from_file_location('_reset_schema_change',Path(__file__).resolve().parents[1]/'aut-04-a12-p03-a02-password-change-schema'/'verify.py')
m=module_from_spec(spec);spec.loader.exec_module(m);f=m.f


def exercise(v):
    db=v['db'];a=f.a;cfg=a.create_migration_config(v['url']);table=PasswordResetResultRow.__table__
    old=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results',
        'auth_password_change_results','aud_events','plt_idempotency_receipts','job_jobs','job_outbox_events',
        'doc_file_objects','prj_projects','lic_installations')
    def snap(include=True):return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t))))
        for t in old+((table.name,) if include else ())}
    before=snap(False);a.command.downgrade(cfg,'20260927_0048');assert snap(False)==before
    a.command.upgrade(cfg,'head');assert snap(False)==before
    assert db.execute('SELECT count(*) FROM plm.auth_password_reset_results').fetchone()==(0,)
    with v['uow']() as tx:
        actual=inspect(tx.session.connection());columns=actual.get_columns(table.name,schema='plm')
        assert set(table.c.keys())=={c['name'] for c in columns} and all(not c['nullable'] for c in columns)
        for c in columns:assert isinstance(c['type'],type(table.c[c['name']].type))
        assert actual.get_pk_constraint(table.name,schema='plm')['constrained_columns']==['result_id']
        assert {c['name'] for c in actual.get_foreign_keys(table.name,schema='plm')}=={c.name for c in table.foreign_key_constraints}
        for kind,getter in (('UniqueConstraint',actual.get_unique_constraints),('CheckConstraint',actual.get_check_constraints)):
            assert {c['name'] for c in getter(table.name,schema='plm')}=={c.name for c in table.constraints if type(c).__name__==kind}
        assert next(c for c in columns if c['name']=='accepted_at')['default']=='statement_timestamp()'
    empty='auth_reset_empty_'+uuid4().hex[:12]
    with f.base.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(empty)))
        try:
            ecfg=a.create_migration_config(v['url'].set(database=empty))
            a.command.upgrade(ecfg,'head');a.command.downgrade(ecfg,'20260927_0048');a.command.upgrade(ecfg,'head')
            with f.base.schema.connect(empty) as conn:assert conn.execute('SELECT count(*) FROM plm.auth_password_reset_results').fetchone()==(0,)
        finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(empty)))
    actor=v['users'][1]
    def seed(name,role='NONE',disabled=False):
        user=f.base.auth.user(db,name,uuid4().bytes*2,role)
        if disabled:
            db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='USER_DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(user,))
            db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(user,))
        return user
    def transition(user,admin=actor,required=True,revoke=True):
        previous,oldid,version,state=db.execute('SELECT lock_version,active_password_credential_id,credential_version,state FROM plm.auth_users WHERE user_id=%s',(user,)).fetchone()
        new=db.execute('''INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,
            parameter_set,must_change_password,changed_by) SELECT user_id,%s,password_hash,algorithm_id,parameter_set,%s,%s
            FROM plm.auth_password_credentials WHERE password_credential_id=%s RETURNING password_credential_id''',
            (version+1,required,admin,oldid)).fetchone()[0]
        changed=db.execute('''UPDATE plm.auth_users SET active_password_credential_id=%s,credential_version=%s,
            lock_version=lock_version+1,updated_by=%s,updated_at=statement_timestamp() WHERE user_id=%s RETURNING updated_at''',
            (new,version+1,admin,user)).fetchone()[0]
        count=0
        if revoke:
            count=db.execute("UPDATE plm.auth_sessions SET revoked_at=%s,revoke_reason='PASSWORD_RESET',lock_version=lock_version+1 WHERE user_id=%s AND revoked_at IS NULL",(changed,user)).rowcount
        trace=uuid4()
        event=db.execute('''INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,
            target_owner_module,target_object_type,target_object_id,before_state,after_state)
            VALUES(%s,'DEPLOYMENT','USER',%s,'PASSWORD_RESET','SUCCESS','auth','AUT-01',%s,%s,%s) RETURNING audit_event_id''',
            (trace,admin,user,f'CREDENTIAL_V{version}',f'CREDENTIAL_V{version+1}')).fetchone()[0]
        return dict(result_id=uuid4(),user_id=user,actor_id=admin,before_credential_id=oldid,credential_id=new,
            before_credential_version=version,credential_version=version+1,before_user_version=previous,user_version=previous+1,
            target_state=state,audit_event_id=event,trace_id=trace,revoked_session_count=count,changed_at=changed)
    def insert(data,conn=db):
        names=tuple(data)
        conn.execute(sql.SQL('INSERT INTO plm.auth_password_reset_results({}) VALUES({})').format(
            sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),tuple(data.values()))
    def deny(data):
        before=snap()
        try:
            with db.transaction():insert(data)
        except psycopg.Error as exc:assert exc.sqlstate in ('P0001','23503','23514','23505','22003'),exc.sqlstate
        else:raise AssertionError('Invalid reset source accepted')
        assert snap()==before
    user=seed('Synthetic reset schema normal')
    import hashlib
    db.execute('''INSERT INTO plm.auth_sessions(user_id,credential_version,session_token_digest,csrf_digest,created_at,
        last_seen_at,idle_expires_at,absolute_expires_at) VALUES(%s,1,%s,%s,statement_timestamp()-interval '1 hour',
        statement_timestamp()-interval '1 hour',statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour')''',
        (user,hashlib.sha256(b'e'*32).digest(),hashlib.sha256(b'c'*32).digest()))
    value=transition(user,revoke=False);deny(value|{'revoked_session_count':2})
    db.execute("UPDATE plm.auth_sessions SET revoked_at=%s,revoke_reason='PASSWORD_RESET',lock_version=lock_version+1 WHERE user_id=%s AND revoked_at IS NULL",(value['changed_at'],user))
    value['revoked_session_count']=2
    for bad in ({'result_id':UUID(int=0)},{'actor_id':v['users'][0]},{'before_credential_id':uuid4()},
        {'credential_id':value['before_credential_id']},{'before_credential_version':0},{'credential_version':3},
        {'before_user_version':value['before_user_version']+1},{'user_version':value['user_version']+1},
        {'target_state':'DISABLED'},{'audit_event_id':uuid4()},{'trace_id':uuid4()},{'revoked_session_count':0},
        {'revoked_session_count':1},{'revoked_session_count':3},{'changed_at':value['changed_at']-timedelta(seconds=1)},
        {'accepted_at':'infinity'},{'accepted_at':value['changed_at']-timedelta(seconds=1)},
        {'accepted_at':value['changed_at']+timedelta(days=1)}):deny(value|bad)
    for field,bad in (('state','DISABLED'),('deployment_role','NONE')):
        before=snap()
        try:
            with db.transaction():
                db.execute(sql.SQL('UPDATE plm.auth_users SET {}=%s WHERE user_id=%s').format(sql.Identifier(field)),(bad,actor))
                insert(value)
        except psycopg.Error as exc:assert exc.sqlstate=='P0001'
        else:raise AssertionError('Invalid Admin accepted')
        assert snap()==before
    before=snap();reached=False
    try:
        with db.transaction():insert(value);reached=True;raise RuntimeError('Synthetic first postinsert fault')
    except RuntimeError:pass
    assert reached and snap()==before
    insert(value)
    accepted=db.execute('SELECT accepted_at FROM plm.auth_password_reset_results WHERE result_id=%s',(value['result_id'],)).fetchone()[0]
    assert PasswordResetResult(**(value|{'accepted_at':accepted})).public_data()=={'credential_version':2}
    deny(value|{'result_id':uuid4()})
    disabled=seed('Synthetic reset schema disabled',disabled=True)
    disabled_value=transition(disabled);assert disabled_value['revoked_session_count']==0 and disabled_value['target_state']=='DISABLED'
    insert(disabled_value)
    self_user=seed('Synthetic reset schema self Admin','DEPLOYMENT_ADMIN')
    self_value=transition(self_user,admin=self_user);insert(self_value)
    # Exact Audit semantics: do not mutate historical Audit, create independent invalid source records.
    for override in ({'actor_id':v['users'][0]},{'action':'PASSWORD_CHANGED'},{'trace_id':uuid4()},
        {'before_state':'CREDENTIAL_V0'},{'after_state':'CREDENTIAL_V3'},{'outcome':'FAILED'}):
        draft=dict(trace_id=value['trace_id'],event_scope='DEPLOYMENT',target_project_id=None,actor_type='USER',
            actor_id=actor,original_actor_id=None,actor_hint_digest=None,action='PASSWORD_RESET',outcome='SUCCESS',
            target_owner_module='auth',target_object_type='AUT-01',target_object_id=user,
            before_state='CREDENTIAL_V1',after_state='CREDENTIAL_V2')
        with v['uow']() as tx:
            wrong=v['audit'].append(tx,f.w.AuditEventDraft(**(draft|override)));tx.commit()
        deny(value|{'result_id':uuid4(),'audit_event_id':wrong})
    # An actual other Admin whose current Credential is restricted cannot become reset authority.
    before=snap();reached=False
    try:
        with db.transaction():
            transition(actor,admin=actor)
            bad=transition(disabled,admin=actor);reached=True;insert(bad)
    except psycopg.Error as exc:assert exc.sqlstate=='P0001' and reached
    else:raise AssertionError('Restricted other Admin source accepted')
    assert snap()==before
    # A second self reset from already restricted Credential cannot bypass normal-Admin precondition.
    before=snap();reached=False
    try:
        with db.transaction():
            bad=transition(self_user,admin=self_user);reached=True;insert(bad)
    except psycopg.Error as exc:assert exc.sqlstate=='P0001' and reached
    else:raise AssertionError('Restricted original self Admin source accepted')
    assert snap()==before
    # Wrong new flag with otherwise consistent root/Audit/count and full-fixture rollback.
    before=snap();reached=False
    try:
        with db.transaction():
            bad=transition(disabled,required=False);reached=True;insert(bad)
    except psycopg.Error as exc:assert exc.sqlstate=='P0001' and reached
    else:raise AssertionError('Normal new Credential accepted as reset')
    assert snap()==before
    # Two independent actual PG connections contend for same first source; exactly one survives.
    raceuser=seed('Synthetic reset schema concurrent');race=transition(raceuser)
    dbname=db.execute('SELECT current_database()').fetchone()[0]
    def compete(index):
        with f.base.schema.connect(dbname) as conn:
            try:insert(race|{'result_id':uuid4()},conn);return 'OK'
            except psycopg.Error as exc:return exc.sqlstate
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(compete,range(2)))
    assert sorted(outcomes)==['23505','OK'],outcomes
    assert db.execute('SELECT count(*) FROM plm.auth_password_reset_results WHERE user_id=%s',(raceuser,)).fetchone()==(1,)
    history=tuple(db.execute('SELECT * FROM plm.auth_password_reset_results ORDER BY result_id'))
    db.execute("UPDATE plm.auth_users SET username_display='Later reset schema name',lock_version=lock_version+1 WHERE user_id=%s",(user,))
    assert tuple(db.execute('SELECT * FROM plm.auth_password_reset_results ORDER BY result_id'))==history
    for query in ('UPDATE plm.auth_password_reset_results SET trace_id=trace_id','DELETE FROM plm.auth_password_reset_results',
        'TRUNCATE plm.auth_password_reset_results'):
        before=snap()
        try:
            with db.transaction():db.execute(query)
        except psycopg.Error as exc:assert exc.sqlstate=='P0001'
        else:raise AssertionError('Reset first history modified')
        assert snap()==before
    before=snap()
    try:a.command.downgrade(cfg,'20260927_0048')
    except Exception as exc:assert getattr(getattr(exc,'orig',None),'sqlstate',None)=='P0001'
    else:raise AssertionError('Reset history lost on downgrade')
    assert snap()==before and db.execute('SELECT version_num FROM plm.alembic_version').fetchone()==('20260927_0049',)
    print('PASS reset schema: real empty/populated0048-49 roundtrip thirteen old tables unchanged/no backfill/ORM parity; normal2 incl expired/disabled0/selfAdmin sources, bad actor/version/state/time/count/normal-new flag reject, first postinsert and full-fixture rollback, independent PG concurrent single first, later identity/immutability/nonempty down head49. TEST_ONLY source; NOT real password/Admin-CSRF-License/atomic reset/HTTP/package proof.')


if __name__=='__main__':f.main(exercise=exercise)
