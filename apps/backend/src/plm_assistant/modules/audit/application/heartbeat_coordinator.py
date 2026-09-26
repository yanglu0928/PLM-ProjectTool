"""Bounded in-process heartbeats; no Job claiming, publication or success inference."""
import math
import threading
from contextlib import contextmanager
from .worker_capture import AuditExportCaptureCommand, AuditExportWorkerError
from plm_assistant.modules.jobs.application.lease import ClaimedJob

_SAFE_ERRORS = frozenset({'AUTH_ACCESS_DENIED','RESOURCE_NOT_FOUND','LICENSE_OPERATION_DENIED',
                         'STALE_LEASE','INCONSISTENT_LEASE','JOB_STORE_UNAVAILABLE','AUDIT_UNAVAILABLE'})


class AuditHeartbeatSupervisor:
    def __init__(self, *, heartbeats, max_workers=4):
        if heartbeats is None or type(max_workers) is not int or not 1 <= max_workers <= 20:
            raise ValueError('Bounded heartbeat dependencies required')
        self._heartbeats, self._max = heartbeats, max_workers
        self._lock, self._jobs = threading.Lock(), {}

    def start(self, command, *, lease_seconds, interval_seconds):
        if type(command) is not AuditExportCaptureCommand:
            raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        if (type(lease_seconds) is not int or not 3 <= lease_seconds <= 3600
                or type(interval_seconds) not in (int,float) or not math.isfinite(interval_seconds)
                or not .01 <= interval_seconds <= lease_seconds/3):
            raise AuditExportWorkerError('VALIDATION_FAILED')
        with self._lock:
            self._jobs = {key:handle for key,handle in self._jobs.items() if handle._thread.is_alive()}
            if command.job_id in self._jobs or len(self._jobs) >= self._max:
                raise AuditExportWorkerError('AUDIT_HEARTBEAT_CAPACITY')
            try:
                handle = _HeartbeatHandle(self, command, lease_seconds, interval_seconds)
                self._jobs[command.job_id] = handle
                handle._thread.start()
            except BaseException:
                self._jobs.pop(command.job_id, None)
                raise AuditExportWorkerError('AUDIT_UNAVAILABLE') from None
        return handle

    def _release(self, handle):
        with self._lock:
            if self._jobs.get(handle._command.job_id) is handle:
                self._jobs.pop(handle._command.job_id)

    @contextmanager
    def stopped(self, command):
        """Short Owner UOW only; block restart in THIS supervisor, never kill I/O.

        Caller must first return from synchronous work and stop its heartbeat.
        Other processes remain constrained by actual Job/fence/Lease facts.
        Do not join or perform file I/O while holding this lock.
        """
        if type(command) is not AuditExportCaptureCommand:
            raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._lock:
            handle = self._jobs.get(command.job_id)
            if handle is not None and handle._thread.is_alive():
                raise AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT')
            if handle is not None:
                self._jobs.pop(command.job_id)
            yield


class _HeartbeatHandle:
    def __init__(self, supervisor, command, seconds, interval):
        self._supervisor, self._command = supervisor, command
        self._seconds, self._interval = seconds, interval
        self._stop, self._ready, self._finished = threading.Event(), threading.Event(), threading.Event()
        self._error = None
        self._thread = threading.Thread(target=self._run, name='plm-audit-heartbeat', daemon=False)

    @property
    def closed(self):
        return self._finished.is_set() and not self._thread.is_alive()

    def _run(self):
        first = None
        try:
            while not self._stop.is_set():
                value = self._supervisor._heartbeats.heartbeat(self._command, lease_seconds=self._seconds)
                if (type(value) is not ClaimedJob or value.job_id != self._command.job_id
                        or value.job_type != 'AUDIT_EXPORT' or type(value.fencing_token) is not int
                        or value.fencing_token != self._command.fencing_token
                        or type(value.attempt_no) is not int or value.attempt_no < 1
                        or type(value.payload_refs) is not dict
                        or value.payload_refs.get('export_id') != str(self._command.export_id)
                        or first is not None and value != first):
                    raise AuditExportWorkerError()
                first = value
                self._ready.set()
                if self._stop.wait(self._interval):
                    break
        except Exception as exc:
            code = exc.code if isinstance(exc, AuditExportWorkerError) and exc.code in _SAFE_ERRORS else 'AUDIT_UNAVAILABLE'
            self._error = code
            self._stop.set()
        finally:
            self._finished.set()
            self._ready.set()

    def check(self):
        if self._error is not None:
            raise AuditExportWorkerError(self._error)
        if self._stop.is_set() or self._finished.is_set():
            raise AuditExportWorkerError('AUDIT_HEARTBEAT_STOPPED')

    def wait_ready(self, *, timeout_seconds=5):
        self._timeout(timeout_seconds)
        if not self._ready.wait(timeout_seconds):
            raise AuditExportWorkerError('AUDIT_HEARTBEAT_NOT_READY')
        self.check()

    @staticmethod
    def _timeout(value):
        if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= 30:
            raise AuditExportWorkerError('VALIDATION_FAILED')

    def stop(self, *, timeout_seconds=5):
        self._timeout(timeout_seconds)
        self._stop.set()
        self._thread.join(timeout_seconds)
        if not self.closed:
            raise AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT')
        self._supervisor._release(self)
        if self._error is not None:
            raise AuditExportWorkerError(self._error)
