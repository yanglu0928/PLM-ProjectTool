"""Interruptible polling of the owned step; no forced kill or guessed shutdown."""
from dataclasses import dataclass
from contextlib import contextmanager
from math import isfinite
from threading import Event,Lock
from time import monotonic
from .worker_step import AuditExportWorkerStep,AuditExportStepOutcome
from .worker_capture import AuditExportWorkerError


@dataclass(frozen=True,slots=True)
class AuditExportLoopResult:
    reason: str
    steps: int
    executed: int
    swept: int
    idle: int
    released: int

    def __post_init__(self):
        counts=(self.steps,self.executed,self.swept,self.idle,self.released)
        if (type(self.reason) is not str or self.reason not in {'STOPPED','LIMIT'}
                or any(type(v) is not int or v<0 for v in counts)
                or self.executed+self.swept+self.idle+self.released>self.steps):raise AuditExportWorkerError()


class AuditExportWorkerLoop:
    def __init__(self,*,step,poll_seconds=1.0):
        if type(step) is not AuditExportWorkerStep or type(poll_seconds) not in (int,float) or not .05<=poll_seconds<=60 or not isfinite(poll_seconds):
            raise ValueError('Owned step and bounded finite poll required')
        self._step,self._seconds,self._wake,self._lock=step,poll_seconds,Event(),Lock()

    def request_stop(self):
        self._step.request_stop();self._wake.set()

    @contextmanager
    def quiescent(self):
        if not self._lock.acquire(blocking=False):raise AuditExportWorkerError('AUDIT_HEARTBEAT_CAPACITY')
        try:
            with self._step.quiescent():yield
        finally:self._lock.release()

    def _wait_idle(self):
        deadline=monotonic()+self._seconds
        while not self._wake.is_set():
            remaining=deadline-monotonic()
            if remaining<=0:return
            self._wake.wait(min(.05,remaining))

    def run(self,*,max_steps=None):
        if max_steps is not None and (type(max_steps) is not int or not 1<=max_steps<=100000):raise AuditExportWorkerError('VALIDATION_FAILED')
        if not self._lock.acquire(blocking=False):raise AuditExportWorkerError('AUDIT_HEARTBEAT_CAPACITY')
        steps=executed=swept=idle=released=0
        try:
            while max_steps is None or steps<max_steps:
                value=self._step.step()
                if type(value) is not AuditExportStepOutcome:raise AuditExportWorkerError()
                value.__post_init__();steps+=1
                if value.kind=='STOPPED':return AuditExportLoopResult('STOPPED',steps,executed,swept,idle,released)
                if value.kind=='EXECUTED':executed+=1
                elif value.kind=='SWEEP_FAILED':swept+=1
                elif value.kind in {'LEASE_EXPIRED','SUPERSEDED'}:released+=1
                elif value.kind=='IDLE':
                    idle+=1
                    if max_steps is None or steps<max_steps:self._wait_idle()
            return AuditExportLoopResult('LIMIT',steps,executed,swept,idle,released)
        except AuditExportWorkerError:raise
        except Exception:raise AuditExportWorkerError() from None
        finally:self._lock.release()
