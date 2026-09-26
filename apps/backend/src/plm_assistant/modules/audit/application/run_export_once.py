"""One bound command lifecycle; no claiming, technical failure writes or process loop."""
import math
from .worker_capture import AuditExportCaptureCommand, AuditExportWorkerError
from .export_result import AuditExportResult


class AuditExportRunOnce:
    def __init__(self, *, worker, supervisor, lease_seconds=60, interval_seconds=10, stop_timeout_seconds=5):
        if (worker is None or supervisor is None or type(lease_seconds) is not int or not 3 <= lease_seconds <= 3600
                or type(interval_seconds) not in (int,float) or not math.isfinite(interval_seconds)
                or not .01 <= interval_seconds <= lease_seconds/3
                or type(stop_timeout_seconds) not in (int,float) or not math.isfinite(stop_timeout_seconds)
                or not 0 <= stop_timeout_seconds <= 30):
            raise ValueError('Bounded single-run dependencies required')
        self._worker,self._supervisor=worker,supervisor
        self._seconds,self._interval,self._stop_timeout=lease_seconds,interval_seconds,stop_timeout_seconds

    @staticmethod
    def _error(exc):
        return AuditExportWorkerError(exc.code if isinstance(exc,AuditExportWorkerError) else 'AUDIT_UNAVAILABLE')

    @staticmethod
    def _result(value, command):
        if type(value) is not AuditExportResult:
            raise AuditExportWorkerError()
        value.__post_init__()
        if value.export_id != command.export_id:
            raise AuditExportWorkerError()
        return value

    def run(self, command):
        if type(command) is not AuditExportCaptureCommand:
            raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        try:
            path=self._worker.classify(command)
            if type(path) is not str:
                raise AuditExportWorkerError()
            if path=='PUBLISHED':
                return self._result(self._worker.recover(command),command)
            if path not in ('RENDER','RECOVER'):
                raise AuditExportWorkerError()
            handle=self._supervisor.start(command,lease_seconds=self._seconds,interval_seconds=self._interval)
        except Exception as exc:
            raise self._error(exc) from None
        failure=None
        try:
            handle.wait_ready(timeout_seconds=self._stop_timeout)
            handle.check()
            if path=='RENDER':
                self._worker.capture(command)
                handle.check()
                staged=self._worker.render(command)
                handle.check()
                self._result(self._worker.publish(command,staged),command)
            else:
                self._result(self._worker.recover(command),command)
        except Exception as exc:
            failure=self._error(exc)
        finally:
            try:handle.stop(timeout_seconds=self._stop_timeout)
            except Exception as exc:
                if failure is None:failure=self._error(exc)
        if handle.closed is not True:
            raise AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT')
        try:
            # Only actual DB success/registered source+full physical hash can resolve
            # lost commit acknowledgement or success-first heartbeat contention.
            return self._result(self._worker.recover(command),command)
        except Exception as exc:
            # Current auth/lease denials take precedence over historical I/O errors.
            if isinstance(exc,AuditExportWorkerError) and exc.code in {
                    'AUTH_ACCESS_DENIED','RESOURCE_NOT_FOUND','LICENSE_OPERATION_DENIED','STALE_LEASE'}:
                raise self._error(exc) from None
            raise failure if failure is not None else self._error(exc) from None
