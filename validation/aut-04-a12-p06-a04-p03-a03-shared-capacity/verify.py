"""Actual PG mixed reset/change share one KDF budget, fresh and history."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier,Lock
from psycopg import sql
from plm_assistant.modules.auth.application.password_capacity import PasswordKdfCapacity

spec=spec_from_file_location('_shared_capacity_atomic',Path(__file__).resolve().parents[1]/'aut-04-a12-p05-a05-reset-atomic'/'verify.py')
r=module_from_spec(spec);spec.loader.exec_module(r);m=r.m;a=r.a


def exercise(v):
    db=v['db'];plain=m.ScryptPasswordHasher();receipts=m.SqlAlchemyIdempotencyReceipts();budget=PasswordKdfCapacity(slots=4)
    mutex=Lock();active=0;peak=0;calls=0
    class ObservedHasher:
        def run(self,method,*args,**kwargs):
            nonlocal active,peak,calls
            with mutex:
                active+=1;peak=max(peak,active);calls+=1
                assert active<=budget.snapshot()['active']<=4
            try:return method(*args,**kwargs)
            finally:
                with mutex:active-=1
        def hash_password(self,password):return self.run(plain.hash_password,password)
        def verify_password(self,password,**kwargs):return self.run(plain.verify_password,password,**kwargs)
    observed=ObservedHasher();createfirst=m.SqlAlchemyUserCreateResultRepository(verifier=plain)
    creator=m.ManagedUserCreateService(unit_of_work=v['uow'],access=m.SqlAlchemyUserCreateAccess(),license_guard=v['guard'],
        users=m.SqlAlchemyUserRepository(),results=createfirst,replay_verifier=m.UserCreateReplayVerifier(source=createfirst),hasher=plain,audit=v['audit'],receipts=receipts)
    sessions=m.SessionService(unit_of_work=v['uow'],repository=m.SqlAlchemySessionRepository(),issue_access=m.SqlAlchemyPasswordIssueAccess(plain),audit=v['audit'],idempotency=receipts)
    old=b'Synthetic shared old';new=b'Synthetic shared new'
    def issue(uid,password):return sessions.issue(user_id=uid,trace_id=uuid4(),proof=m.PasswordIssueProof(bytearray(password)))
    resetfirst=r.SqlAlchemyPasswordResetResults(verifier=observed)
    resets=r.PasswordResetService(unit_of_work=v['uow'],access=r.SqlAlchemyPasswordResetAccess(verifier=observed),repository=r.SqlAlchemyPasswordResetRepository(),
        results=resetfirst,replay_verifier=r.PasswordResetReplayVerifier(source=resetfirst),hasher=observed,audit=v['audit'],receipts=receipts,license_guard=v['guard'],capacity=budget)
    changefirst=a.SqlAlchemyPasswordChangeResults(verifier=observed)
    changes=a.PasswordChangeService(unit_of_work=v['uow'],access=a.SqlAlchemyPasswordChangeAccess(verifier=observed),repository=a.SqlAlchemyPasswordChangeRepository(),
        results=changefirst,replay_verifier=a.PasswordChangeReplayVerifier(source=changefirst),hasher=observed,audit=v['audit'],receipts=receipts,capacity=budget)
    rows=[]
    for i in range(20):
        user=creator.create(m.CreateManagedUser(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),f'Synthetic shared capacity {i}',bytearray(old)),idempotency_key=str(uuid4()))
        rows.append((user.user_id,issue(user.user_id,old),str(uuid4()),'reset' if i%2==0 else 'change'))
    def command(row,session=None):
        uid,initial,key,kind=row
        if kind=='reset':return r.ResetPassword(v['tokens'][1],m.fixture.base.auth.CSRF,uuid4(),uid,1,True,r.PasswordResetProof(bytearray(new)))
        current=initial if session is None else session
        return a.ChangePassword(current.token,current.csrf_token,uuid4(),a.PasswordChangeProof(bytearray(old),bytearray(new)))
    def batch(history=False):
        barrier=Barrier(20)
        commands=[command(row,issue(row[0],new) if history and row[3]=='change' else None) for row in rows]
        def run(pair):
            row,cmd=pair;barrier.wait(timeout=10)
            result=(resets.reset(cmd,idempotency_key=row[2]) if row[3]=='reset' else changes.change(cmd,idempotency_key=row[2]))
            if row[3]=='reset':assert not any(cmd.password.temporary_password)
            else:assert not any(cmd.passwords.current_password) and not any(cmd.passwords.new_password)
            return result
        with ThreadPoolExecutor(max_workers=20) as pool:return list(pool.map(run,zip(rows,commands,strict=True)))
    firsts=batch()
    assert calls==30 and active==0 and peak==4 and budget.snapshot()=={'slots':4,'active':0,'peak':4}
    for row,first in zip(rows,firsts,strict=True):
        assert first.user_id==row[0] and first.credential_version==2
        assert db.execute('SELECT credential_version,lock_version FROM plm.auth_users WHERE user_id=%s',(row[0],)).fetchone()==(2,2)
        try:sessions.validate(row[1].token)
        except m.SessionError as exc:assert exc.code=='AUTH_SESSION_EXPIRED'
        else:raise AssertionError('Old mixed Session survived')
    # Issue the history identities before taking the no-write snapshot.
    history_sessions={uid:issue(uid,new) for uid,initial,key,kind in rows if kind=='change'}
    tables=('auth_users','auth_password_credentials','auth_sessions','auth_user_create_results','auth_user_state_results','auth_password_change_results','auth_password_reset_results','aud_events','plt_idempotency_receipts')
    def snap():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    before=snap();barrier=Barrier(20)
    def replay(row):
        cmd=command(row,history_sessions.get(row[0]));barrier.wait(timeout=10)
        got=resets.reset(cmd,idempotency_key=row[2]) if row[3]=='reset' else changes.change(cmd,idempotency_key=row[2])
        if row[3]=='reset':assert not any(cmd.password.temporary_password)
        else:assert not any(cmd.passwords.current_password) and not any(cmd.passwords.new_password)
        return got
    with ThreadPoolExecutor(max_workers=20) as pool:replayed=list(pool.map(replay,rows))
    assert replayed==firsts and snap()==before and calls==60 and active==0 and peak==4
    assert budget.snapshot()=={'slots':4,'active':0,'peak':4}
    print('PASS actual mixed PG/Scrypt: 10reset+10change concurrent fresh and history share exactly one 4-slot budget; each phase30 true KDF calls, combined peak4/end0, all20 original results/version2/old Sessions revoked, history nine tables unchanged and buffers erased. Internal explicit injection only; Windows bootstrap/whole Auth/cross-process/latency/package not claimed.')


if __name__=='__main__':m.fixture.main(exercise=lambda v:(exercise(v),r.exercise(v)))
