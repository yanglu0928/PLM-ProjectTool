"""External CTRL_BREAK to an exclusively owned hidden Windows console."""
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

CHILD = r'''
import signal,sys
from threading import Event,Thread
from time import monotonic
from unit.test_audit_worker_loop import WorkerLoopTests
from plm_assistant.entrypoints.audit_worker_signals import audit_worker_signals
f=WorkerLoopTests();f.setUp();loop=f.loop;before=signal.getsignal(signal.SIGBREAK)
released=Event()
def control():
    for line in sys.stdin:
        if line.strip()=='RELEASE':released.set()
        if line.strip()=='STOP':loop.request_stop();released.set();return
t=Thread(target=control,daemon=True);t.start()
if sys.argv[1]=='idle':
    f.t.admission.claim_next.return_value=None;loop._seconds=60
else:
    outcome=f.t.executor.execute.return_value
    def execute(command):
        print('ACTIVE',flush=True)
        deadline=monotonic()+10
        while not released.wait(.05):
            assert monotonic()<deadline
        return outcome
    f.t.executor.execute.side_effect=execute
with audit_worker_signals(loop):
    print('READY',flush=True);started=monotonic();result=loop.run()
assert result.reason=='STOPPED' and signal.getsignal(signal.SIGBREAK) is before
if sys.argv[1]=='idle':assert result.executed==0 and monotonic()-started<5
else:
    assert result.executed==1
    f.t.admission.claim_next.assert_called_once()
assert loop._step._pending is None
print('PASS',flush=True)
'''

SENDER = r'''
import ctypes,os,sys,time
from ctypes import wintypes as w
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.AttachConsole.argtypes=[w.DWORD];k.AttachConsole.restype=w.BOOL
k.GetConsoleProcessList.argtypes=[ctypes.POINTER(w.DWORD),w.DWORD];k.GetConsoleProcessList.restype=w.DWORD
handler_type=ctypes.WINFUNCTYPE(w.BOOL,w.DWORD)
k.SetConsoleCtrlHandler.argtypes=[handler_type,w.BOOL];k.SetConsoleCtrlHandler.restype=w.BOOL
k.GenerateConsoleCtrlEvent.argtypes=[w.DWORD,w.DWORD];k.GenerateConsoleCtrlEvent.restype=w.BOOL
pid=int(sys.argv[1]);k.FreeConsole()
assert k.AttachConsole(pid)
try:
    entries=(w.DWORD*16)();count=k.GetConsoleProcessList(entries,16)
    assert count==2 and set(entries[:count])=={pid,os.getpid()}
    handler=handler_type(lambda event: True)
    assert k.SetConsoleCtrlHandler(handler,True)
    assert k.GenerateConsoleCtrlEvent(1,0)
    time.sleep(.2)
finally:k.FreeConsole()
'''

def main():
    if sys.platform!='win32':raise RuntimeError('Windows-only verification')
    root=Path(__file__).resolve().parents[2];env=dict(os.environ)
    env['PYTHONPATH']=str(root/'apps/backend/tests')+os.pathsep+env.get('PYTHONPATH','')
    for mode in ('idle','active'):
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        child=subprocess.Popen([sys.executable,'-c',CHILD,mode],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        lines=queue.Queue()
        def read(stream=child.stdout):
            for line in stream:lines.put(line.strip())
        reader=threading.Thread(target=read);reader.start()
        def expect(value):
            actual=lines.get(timeout=15)
            if actual!=value:raise RuntimeError('Unexpected synthetic child state: '+actual)
        try:
            expect('READY')
            if mode=='active':expect('ACTIVE')
            assert child.poll() is None
            sender=subprocess.run([sys.executable,'-c',SENDER,str(child.pid)],capture_output=True,text=True,timeout=10)
            if sender.returncode:raise RuntimeError('Console sender refused or failed')
            if mode=='active':child.stdin.write('RELEASE\n');child.stdin.flush()
            expect('PASS');assert child.wait(timeout=10)==0
        finally:
            if child.poll() is None:
                child.stdin.write('STOP\n');child.stdin.flush()
                child.wait(timeout=15)
            reader.join(timeout=2)
            child.stdin.close();child.stdout.close()
    print('P12-A PASS: external CTRL_BREAK, isolated consoles, idle stop and active single-command drain. Synthetic executor only; no DB/SCM/production readiness claim.')

if __name__=='__main__':main()
