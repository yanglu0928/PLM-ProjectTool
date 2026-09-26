"""Independent synthetic processes: actual interpreter SIGINT, not Console control."""
import os
from pathlib import Path
import subprocess
import sys


CHILD=r'''
import signal,sys
from threading import Event,Thread
from time import monotonic
from unit.test_audit_worker_loop import WorkerLoopTests
from plm_assistant.entrypoints.audit_worker_signals import run_audit_worker_process
f=WorkerLoopTests();f.setUp();loop=f.loop;previous=signal.getsignal(signal.SIGINT)
if sys.argv[1]=='idle':
    f.t.admission.claim_next.return_value=None
    waiting=Event();original=loop._wake.wait
    def wait(seconds):waiting.set();return original(seconds)
    loop._wake.wait=wait;loop._seconds=60
    def send():
        assert waiting.wait(2);signal.raise_signal(signal.SIGINT)
    sender=Thread(target=send);sender.start();started=monotonic()
    result=run_audit_worker_process(loop);sender.join(timeout=2)
    assert not sender.is_alive() and monotonic()-started<2 and result.reason=='STOPPED' and result.executed==0
else:
    outcome=f.t.executor.execute.return_value;finished=Event()
    def execute(c):
        signal.raise_signal(signal.SIGINT);Event().wait(.15);finished.set();return outcome
    f.t.executor.execute.side_effect=execute
    result=run_audit_worker_process(loop)
    assert result.reason=='STOPPED' and result.executed==1 and finished.is_set()
    f.t.admission.claim_next.assert_called_once()
assert signal.getsignal(signal.SIGINT) is previous and loop._step._pending is None
print('SYNTHETIC_SIGNAL_PASS')
'''


def main():
    env=dict(os.environ);root=Path(__file__).resolve().parents[2]
    env['PYTHONPATH']=str(root/'apps/backend/tests')+os.pathsep+env.get('PYTHONPATH','')
    for mode in ('idle','active'):
        result=subprocess.run([sys.executable,'-c',CHILD,mode],env=env,capture_output=True,text=True,timeout=15)
        if result.returncode!=0 or result.stdout.strip()!='SYNTHETIC_SIGNAL_PASS':raise RuntimeError('Synthetic signal child failed')
    print('P06-P10 PASS: two independent synthetic Windows Python processes actual SIGINT idle60s prompt stop and active known-command drain/one claim, true STOPPED and exact original handler restoration. No DB/customer/secret sends or forced termination. External Console Ctrl-C/Break, SCM, SIGTERM hard termination, production sources, other platforms/package NOT proved.')


if __name__=='__main__':main()
