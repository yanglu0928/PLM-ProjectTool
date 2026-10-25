"""Actual current Admin/CSRF, Scrypt, atomic receipts/history and lost commit confirmation."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from psycopg import sql
from sqlalchemy import text
from plm_assistant.modules.auth.application.managed_user_create import (
    CreateManagedUser,ManagedUserCreateService,ManagedUserCreateError,OPERATION)
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayVerifier
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.application.session_service import PasswordIssueProof
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.user_create_access import SqlAlchemyUserCreateAccess
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts

spec=spec_from_file_location('_user_atomic_publication',Path(__file__).resolve().parents[1]
    /'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];hasher=ScryptPasswordHasher();users=SqlAlchemyUserRepository()
    results=SqlAlchemyUserCreateResultRepository(verifier=hasher);receipts=SqlAlchemyIdempotencyReceipts()
    deps=dict(unit_of_work=v['uow'],access=SqlAlchemyUserCreateAccess(),license_guard=v['guard'],users=users,
        results=results,replay_verifier=UserCreateReplayVerifier(source=results),hasher=hasher,audit=v['audit'],receipts=receipts)
    service=ManagedUserCreateService(**deps)
    tables=('auth_users','auth_password_credentials','auth_sessions','aud_events','plt_idempotency_receipts','auth_user_create_results')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    password='  合成原子密码-é  '
    def command(name='Synthetic atomic user',secret=password,token=None,csrf=None):
        return CreateManagedUser(v['tokens'][1] if token is None else token,
            fixture.base.auth.CSRF if csrf is None else csrf,uuid4(),name,bytearray(secret.encode()))
    def run(cmd,key,owner=service):
        try:return owner.create(cmd,idempotency_key=key)
        finally:assert not any(cmd.password)
    def reject(cmd,key,code,owner=service):
        before=snapshot()
        try:run(cmd,key,owner)
        except ManagedUserCreateError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('Unsafe atomic User creation accepted')
        assert snapshot()==before
    key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        views=list(pool.map(lambda _:run(command(),key),range(2)))
    first=views[0];assert views[1]==first
    assert first.account_state=='ENABLED' and first.deployment_role=='NONE' and first.lock_version==first.credential_version==1
    assert db.execute('SELECT count(*) FROM plm.auth_password_credentials WHERE user_id=%s',(first.user_id,)).fetchone()==(1,)
    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='USER_CREATED' AND target_object_id=%s",(first.user_id,)).fetchone()==(1,)
    assert db.execute('SELECT count(*) FROM plm.auth_user_create_results WHERE user_id=%s',(first.user_id,)).fetchone()==(1,)
    assert db.execute('SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation=%s AND result_ref_id=%s',
        (OPERATION,first.user_id)).fetchone()==(1,)
    before=snapshot();assert run(command(),key)==first;assert snapshot()==before
    with v['uow']() as tx:
        proof=PasswordIssueProof(bytearray(password.encode()))
        try:assert SqlAlchemyPasswordIssueAccess(hasher).can_issue(tx,first.user_id,1,proof) is True
        finally:proof.erase()
    assert snapshot()==before
    reject(command(secret='Different synthetic password'),key,'CONFLICT_IDEMPOTENCY')
    reject(command(name='Different synthetic username'),key,'CONFLICT_IDEMPOTENCY')
    reject(command(name='SYNTHETIC ATOMIC USER'),str(uuid4()),'AUTH_USERNAME_CONFLICT')
    for token,csrf in ((v['tokens'][0],None),(b'?'*32,None),(None,b'?'*32)):
        reject(command(token=token,csrf=csrf),str(uuid4()),'AUTH_ACCESS_DENIED')
        reject(command(token=token,csrf=csrf),key,'AUTH_ACCESS_DENIED')
    # Same key with competing distinct passwords: precisely one first identity wins.
    raced_key=str(uuid4())
    def competing(index):
        cmd=command('Synthetic distinct password race','Synthetic race password '+str(index))
        try:return ('ok',run(cmd,raced_key))
        except ManagedUserCreateError as exc:return (exc.code,None)
    with ThreadPoolExecutor(max_workers=2) as pool:raced=list(pool.map(competing,range(2)))
    assert sorted(r[0] for r in raced)==['CONFLICT_IDEMPOTENCY','ok']
    assert db.execute("SELECT count(*) FROM plm.auth_users WHERE username_normalized='synthetic distinct password race'").fetchone()==(1,)
    # Later target changes are fixtures, not password-reset or disable production commands.
    secret2=bytearray(b'Synthetic new credential2');view=memoryview(secret2)
    try:new_hash=hasher.hash_password(view)
    finally:view.release();secret2[:]=b'\x00'*len(secret2)
    with v['uow']() as tx:
        credential2=tx.session.execute(text("""INSERT INTO plm.auth_password_credentials(user_id,credential_version,
            password_hash,algorithm_id,parameter_set,changed_by) VALUES(:user,2,:hash,:algorithm,
            CAST(:parameters AS jsonb),:actor) RETURNING password_credential_id"""),
            dict(user=first.user_id,hash=new_hash.password_hash,algorithm=new_hash.algorithm_id,
                 parameters='{"n":131072,"r":8,"p":1,"dklen":32}',actor=v['users'][1])).scalar_one()
        tx.session.execute(text("UPDATE plm.auth_users SET active_password_credential_id=:credential,credential_version=2,"
            "state='DISABLED',username_display='Synthetic later name',lock_version=2,updated_at=statement_timestamp() "
            "WHERE user_id=:user"),dict(credential=credential2,user=first.user_id))
        tx.commit()
    before=snapshot();assert run(command(),key)==first;assert snapshot()==before
    reject(command(secret='Synthetic new credential2'),key,'CONFLICT_IDEMPOTENCY')
    assert db.execute('SELECT state,credential_version,lock_version FROM plm.auth_users WHERE user_id=%s',
        (first.user_id,)).fetchone()==('DISABLED',2,2)
    for column,value,restore in (('deployment_role','NONE','DEPLOYMENT_ADMIN'),('state','DISABLED','ENABLED')):
        db.execute(sql.SQL('UPDATE plm.auth_users SET {}=%s WHERE user_id=%s').format(sql.Identifier(column)),(value,v['users'][1]))
        try:reject(command(),key,'AUTH_ACCESS_DENIED')
        finally:db.execute(sql.SQL('UPDATE plm.auth_users SET {}=%s WHERE user_id=%s').format(sql.Identifier(column)),(restore,v['users'][1]))
    revoked=b'z'*32
    revoked_user=fixture.base.auth.user(db,'Synthetic revoked create admin',revoked,'DEPLOYMENT_ADMIN')
    db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='ADMIN_REVOKED',"
        "lock_version=lock_version+1 WHERE user_id=%s",(revoked_user,))
    reject(command(token=revoked),str(uuid4()),'AUTH_ACCESS_DENIED')
    v['guard'].enabled=False
    try:reject(command(),key,'LICENSE_OPERATION_DENIED')
    finally:v['guard'].enabled=True
    # Each wrapper performs actual write first, then faults; no partial state/receipt/Audit survives.
    fault_reached=set()
    class BrokenUsers:
        def __init__(self,step):self.step=step
        def add_user(self,*args,**kw):
            value=users.add_user(*args,**kw)
            if self.step=='user':fault_reached.add('user');raise RuntimeError('Synthetic after User write')
            return value
        def add_credential(self,*args,**kw):
            value=users.add_credential(*args,**kw)
            if self.step=='credential':fault_reached.add('credential');raise RuntimeError('Synthetic after Credential write')
            return value
        def activate_initial_credential(self,*args,**kw):
            value=users.activate_initial_credential(*args,**kw)
            if self.step=='activate':fault_reached.add('activate');raise RuntimeError('Synthetic after activation write')
            return value
    class BrokenAudit:
        def append(self,*args,**kw):v['audit'].append(*args,**kw);fault_reached.add('audit');raise RuntimeError('Synthetic after Audit write')
    class BrokenResults:
        def record(self,*args,**kw):results.record(*args,**kw);fault_reached.add('result');raise RuntimeError('Synthetic after first-result write')
    class BrokenReceipts:
        def __init__(self,step):self.step=step
        def reserve(self,*args,**kw):
            value=receipts.reserve(*args,**kw)
            if self.step=='reserve':fault_reached.add('reserve');raise RuntimeError('Synthetic after reserve write')
            return value
        def complete(self,*args,**kw):
            receipts.complete(*args,**kw)
            fault_reached.add(self.step)
            if self.step=='complete':raise RuntimeError('Synthetic after receipt complete')
            if self.step=='license':v['guard'].enabled=False
            if self.step=='revoke':
                args[0].session.execute(text("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),"
                    "revoke_reason='ADMIN_REVOKED',lock_version=lock_version+1 WHERE user_id=:actor"),dict(actor=v['users'][1]))
    faults=[{'users':BrokenUsers(s)} for s in ('user','credential','activate')]
    faults += [{'audit':BrokenAudit()},{'results':BrokenResults()}]
    faults += [{'receipts':BrokenReceipts(s)} for s in ('reserve','complete','license','revoke')]
    for index,override in enumerate(faults):
        code='LICENSE_OPERATION_DENIED' if index==7 else 'AUTH_ACCESS_DENIED' if index==8 else 'AUTH_CREATE_UNAVAILABLE'
        try:reject(command('Synthetic atomic fault '+str(index)),str(uuid4()),code,ManagedUserCreateService(**(deps|override)))
        finally:v['guard'].enabled=True
    assert fault_reached=={'user','credential','activate','audit','result','reserve','complete','license','revoke'}
    class BadHasher:
        def hash_password(self,_):return PasswordHashResult('MALFORMED_SOURCE','SCRYPT',{'n':131072})
    reject(command('Synthetic invalid hash source'),str(uuid4()),'AUTH_CREATE_UNAVAILABLE',
        ManagedUserCreateService(**(deps|{'hasher':BadHasher()})))
    now=datetime.now(timezone.utc);times=iter((now,now+timedelta(hours=2)))
    reject(command('Synthetic expires before commit'),str(uuid4()),'AUTH_ACCESS_DENIED',
        ManagedUserCreateService(**(deps|{'clock':lambda:next(times)})))
    with patch('hashlib.scrypt',side_effect=ValueError('Synthetic KDF resource failure')):
        reject(command('Synthetic KDF unavailable'),str(uuid4()),'AUTH_CREATE_UNAVAILABLE')
        reject(command(),key,'AUTH_CREATE_UNAVAILABLE')
    # Both sides of commit uncertainty: before commit all rollback; after commit same-key recovery only.
    commit_reached={False:False,True:False}
    class UncertainCommit:
        def __init__(self,after):self.inner=v['uow']();self.after=after;self.tx=None
        @property
        def session(self):return self.tx.session
        def __enter__(self):self.tx=self.inner.__enter__();return self
        def __exit__(self,*args):return self.inner.__exit__(*args)
        def commit(self):
            commit_reached[self.after]=True
            if self.after:self.tx.commit()
            raise RuntimeError('Synthetic commit confirmation lost')
    reject(command('Synthetic precommit fault'),str(uuid4()),'AUTH_CREATE_UNAVAILABLE',
        ManagedUserCreateService(**(deps|{'unit_of_work':lambda:UncertainCommit(False)})))
    unknown_key=str(uuid4());before=snapshot()
    try:run(command('Synthetic committed unknown'),unknown_key,
        ManagedUserCreateService(**(deps|{'unit_of_work':lambda:UncertainCommit(True)})))
    except ManagedUserCreateError as exc:assert exc.code=='AUTH_CREATE_UNAVAILABLE'
    else:raise AssertionError('Lost confirmation guessed successful')
    assert all(commit_reached.values()),'Actual commit boundary must be reached in both fault cases'
    assert snapshot()!=before
    committed=snapshot();recovered=run(command('Synthetic committed unknown'),unknown_key);assert snapshot()==committed
    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='USER_CREATED' AND target_object_id=%s",
        (recovered.user_id,)).fetchone()==(1,)
    print('Atomic User create PASS: actual current Admin Session-CSRF/Scrypt and same-UOW User/Credential1/Audit/'
        'immutable first/receipt; same-key two callers single identity, distinct-password race one conflict; original '
        'password authentication proof and later disabled/renamed/credential2 target replay unchanged, never revived. '
        'Wrong password/username/canonical/ordinary-revoked-role-state-CSRF-License deny; nine postwrite faults, '
        'malformed hash, KDF, final actual Session revocation/expiry and precommit fault six-table full rollback. '
        'Actual committed-then-confirmation-fault not guessed, same-key replay recovers without writes/duplicate Audit. '
        'Buffers erased; License positive synthetic/guard pre-post not business-UOW lock. HTTP/Windows write/20-concurrent '
        'performance/formal trust/three-platform/Gate/usable package remain unproven.')


if __name__=='__main__':fixture.main(exercise=exercise)
