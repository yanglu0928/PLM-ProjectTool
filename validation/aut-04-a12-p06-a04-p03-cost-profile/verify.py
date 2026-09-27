"""Test-only timing of real KDF, capacity wait and DB lock/UOW boundaries."""
import json
import math
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Lock,BoundedSemaphore
from time import perf_counter
from unittest.mock import patch
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.user_state_access import SqlAlchemyUserStateAccess
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork

spec=spec_from_file_location('_password_cost_calibration',Path(__file__).resolve().parents[1]/'aut-04-a12-p06-a04-p01-resource-calibration'/'verify.py')
c=module_from_spec(spec);spec.loader.exec_module(c);b=c.bench


class Profile:
    def __init__(self):self.lock=Lock();self.group=None;self.samples={}
    def add(self,kind,elapsed):
        with self.lock:
            if self.group is not None:self.samples.setdefault((self.group,kind),[]).append(elapsed*1000)
    def report(self,group):
        with self.lock:rows={kind:sorted(values) for (name,kind),values in self.samples.items() if name==group}
        return {kind:{'calls':len(values),'total_ms':round(sum(values),3),'min_ms':round(values[0],3),
            'median_ms':round(values[len(values)//2],3),'p95_ms':round(values[math.ceil(.95*len(values))-1],3),
            'max_ms':round(values[-1],3)} for kind,values in sorted(rows.items())}


class Slots:
    def __init__(self,profile):self.gate=BoundedSemaphore(4);self.profile=profile
    def acquire(self,*,timeout):
        start=perf_counter()
        result=self.gate.acquire(timeout=timeout)
        self.profile.add('slot_wait_success' if result else 'slot_wait_timeout',perf_counter()-start)
        return result
    def release(self):self.gate.release()


def main():
    profile=Profile();groups=iter(('session_get','reset_fresh','change_fresh','reset_replay','change_replay'));seen=[]
    batch=b.batch;hash_password=ScryptPasswordHasher.hash_password;verify_password=ScryptPasswordHasher.verify_password
    enter=SqlAlchemyUnitOfWork.__enter__;leave=SqlAlchemyUnitOfWork.__exit__;lock=SqlAlchemyUserStateAccess.lock_deployment
    async def measured_batch(app,requests):
        name=next(groups);profile.group=name;seen.append(name)
        start=perf_counter()
        try:return await batch(app,requests)
        finally:
            profile.add('batch_wall',perf_counter()-start)
            profile.group=None
            report=profile.report(name)
            print('PASSWORD_COST_PROFILE '+json.dumps({'group':name,'concurrency':20,'production_slots':4,'stages':report},sort_keys=True))
    def timed_hash(self,password):
        start=perf_counter()
        try:return hash_password(self,password)
        finally:profile.add('scrypt_hash',perf_counter()-start)
    def timed_verify(self,password,**kwargs):
        start=perf_counter()
        try:return verify_password(self,password,**kwargs)
        finally:profile.add('scrypt_verify',perf_counter()-start)
    def timed_enter(self):
        result=enter(self);self._poc_cost_start=perf_counter();self._poc_cost_global=None;return result
    def timed_leave(self,*args):
        try:return leave(self,*args)
        finally:
            end=perf_counter()
            profile.add('uow_with_global' if self._poc_cost_global is not None else 'uow_without_global',end-self._poc_cost_start)
            if self._poc_cost_global is not None:profile.add('global_lock_hold_until_uow_exit',end-self._poc_cost_global)
    def timed_lock(self,tx):
        start=perf_counter()
        try:
            result=lock(self,tx)
            if result is True:tx._poc_cost_global=perf_counter()
            return result
        finally:profile.add('global_lock_acquire',perf_counter()-start)
    with patch.object(b,'batch',measured_batch),patch.object(ScryptPasswordHasher,'hash_password',timed_hash),\
        patch.object(ScryptPasswordHasher,'verify_password',timed_verify),\
        patch.object(SqlAlchemyUnitOfWork,'__enter__',timed_enter),patch.object(SqlAlchemyUnitOfWork,'__exit__',timed_leave),\
        patch.object(SqlAlchemyUserStateAccess,'lock_deployment',timed_lock),\
        patch.object(c.password_reset,'_RESET_HASH_SLOTS',Slots(profile)),patch.object(c.password_change,'_CHANGE_KDF_SLOTS',Slots(profile)):
        b.windows.http.m.fixture.main(exercise=lambda v:b.windows.exercise(v,extra=lambda ctx,settings:b.extra(ctx,settings,include_replay=True)))
    assert seen==['session_get','reset_fresh','change_fresh','reset_replay','change_replay']
    for group in seen:
        rows=profile.report(group)
        assert rows['batch_wall']['calls']==1
        if group=='session_get':assert not any(kind.startswith('scrypt_') for kind in rows)
        else:
            assert rows['slot_wait_success']['calls']==20 and 'slot_wait_timeout' not in rows
            assert rows['global_lock_acquire']['calls']==rows['global_lock_hold_until_uow_exit']['calls']==20
            assert sum(rows.get(kind,{}).get('calls',0) for kind in ('scrypt_hash','scrypt_verify'))==(40 if group.startswith('change') else 20)
    print('PASSWORD_COST_PROFILE_SUMMARY '+json.dumps({'instrumentation_only':True,'production_changed':False,
        'process_peak_working_set_bytes':c.peak_working_set(),'original_acceptance_pass':b.OUTCOME==[True],
        'scope':'stage sample percentiles are not additive; UOW count includes all endpoint identity and response reads; ASGI/synthetic trust not formal load'},sort_keys=True))
    if b.OUTCOME!=[True]:raise SystemExit('PASSWORD_COST_PROFILE FAIL: original performance thresholds remain')


if __name__=='__main__':main()
