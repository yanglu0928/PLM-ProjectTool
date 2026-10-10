"""Real owned step chain through the bounded loop, no service/installer claim."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from plm_assistant.modules.audit.application.worker_loop import AuditExportWorkerLoop

spec=spec_from_file_location('_loop_step_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a07-p04-p03-p06-p07-worker-step'/'verify.py')
p=module_from_spec(spec);spec.loader.exec_module(p)


def exercise(v):
    def decorate(step):
        loop=AuditExportWorkerLoop(step=step,poll_seconds=.05)
        original=step.step;values=[]
        def counted():
            value=original();values.append(value);return value
        step.step=counted
        class Wrapped:
            def request_stop(self):loop.request_stop()
            def step(self):
                result=loop.run(max_steps=1);value=values.pop();assert not values
                assert result.steps==1 and result.reason==('STOPPED' if value.kind=='STOPPED' else 'LIMIT')
                assert result.executed==(value.kind=='EXECUTED') and result.idle==(value.kind=='IDLE')
                return value
        return Wrapped()
    p.exercise(v,decorate_step=decorate)
    print('P06-P08 PASS: actual bounded PG dualScope pending admission/shared periodic heartbeat/publication and current User denial through actual bounded Loop; idle/stop no DB writes and LIMIT never falsely STOPPED. Real interruptible Event.wait/parallel-run refusal/pending drain unit tested, no real service process/signals/production/package proof.')


if __name__=='__main__':p.fixture.main(exercise=exercise)
