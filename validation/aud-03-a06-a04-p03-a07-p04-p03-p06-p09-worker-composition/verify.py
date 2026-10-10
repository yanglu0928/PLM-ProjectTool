"""Actual fixed owned composition root against isolated PG18/Vault sources."""
from contextlib import contextmanager
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings

spec=spec_from_file_location('_composition_step_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a07-p04-p03-p06-p07-worker-step'/'verify.py')
p=module_from_spec(spec);spec.loader.exec_module(p)


def exercise(v):
    database=p.e.create_worker_database_runtime(v['url']);original_uow=database.unit_of_work
    @contextmanager
    def counted_uow():
        with original_uow() as tx:
            v['active'][0]+=1
            try:yield tx
            finally:v['active'][0]-=1
    database.unit_of_work=counted_uow
    def decorate(unused):
        loop=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],
            settings=AuditWorkerSettings('composition-real',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
        step=loop._step;original=step.step;values=[]
        def counted():
            value=original();values.append(value);return value
        step.step=counted
        class Wrapped:
            def request_stop(self):loop.request_stop()
            def step(self):
                result=loop.run(max_steps=1);value=values.pop();assert not values
                assert result.steps==1 and result.reason==('STOPPED' if value.kind=='STOPPED' else 'LIMIT')
                return value
        return Wrapped()
    try:p.exercise(v,decorate_step=decorate)
    finally:database.dispose()
    print('P06-P09 PASS: actual owned factory startup bounded PG18/current full migration head/current temporary Vault identity; dualScope real queue/admission/heartbeat/publish/current User denial through actual Loop; stop/idle readonly. License synthetic, no formal source/CLI/signals/production account/service/package proof.')


if __name__=='__main__':p.fixture.main(exercise=exercise)
