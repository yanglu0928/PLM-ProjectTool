"""Minimal signal callback; normal bridge thread requests owned graceful stop."""
from contextlib import contextmanager
import signal
from threading import Event,Lock,Thread,current_thread,main_thread
from plm_assistant.modules.audit.application.worker_loop import AuditExportWorkerLoop

_registration=Lock()
_poisoned=False


@contextmanager
def audit_worker_signals(loop):
    global _poisoned
    if type(loop) is not AuditExportWorkerLoop or current_thread() is not main_thread():raise RuntimeError('Audit worker signal adapter unavailable')
    if _poisoned or not _registration.acquire(blocking=False):raise RuntimeError('Audit worker signal adapter unavailable')
    requested=[False];halt=Event();installed=[];bridge=None;clean=True
    def handler(signum,frame):requested[0]=True  # NO locks, DB, logging, or file I/O.
    def relay():
        while not halt.wait(.05):
            if requested[0]:loop.request_stop();return
    try:
        signals=(signal.SIGINT,signal.SIGTERM)+((signal.SIGBREAK,) if hasattr(signal,'SIGBREAK') else ())
        for number in signals:
            previous=signal.getsignal(number)
            signal.signal(number,handler);installed.append((number,previous))
        bridge=Thread(target=relay,name='plm-audit-stop-relay',daemon=False);bridge.start()
        yield
    finally:
        halt.set()
        if bridge is not None and bridge.ident is not None:
            bridge.join(timeout=2)
            if bridge.is_alive():clean=False
        for number,previous in reversed(installed):
            try:signal.signal(number,previous)
            except Exception:clean=False
        if not clean:_poisoned=True
        _registration.release()
        if not clean:raise RuntimeError('Audit worker signal adapter unavailable; process restart required') from None


def run_audit_worker_process(loop,*,max_steps=None):
    if max_steps is not None and (type(max_steps) is not int or not 1<=max_steps<=100000):raise ValueError('Bounded step count required')
    try:
        with audit_worker_signals(loop):return loop.run(max_steps=max_steps)
    except Exception:raise RuntimeError('Audit worker process unavailable') from None
