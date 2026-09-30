"""Minimal Windows SCM dispatcher; business workloads are wired separately."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from threading import Event, Lock
from typing import Callable


SERVICE_NAMES = {
    "API": "PLMProjectToolApi",
    "AUDIT_WORKER": "PLMProjectToolAuditWorker",
    "PARSER_WORKER": "PLMProjectToolParserWorker",
}
START_PENDING = 2
STOP_PENDING = 3
RUNNING = 4
STOPPED = 1
SERVICE_ACCEPT_STOP = 1
SERVICE_CONTROL_STOP = 1
SERVICE_WIN32_OWN_PROCESS = 0x10
ERROR_SERVICE_SPECIFIC_ERROR = 1066


class WindowsServiceDispatcherError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_SERVICE_DISPATCHER_UNAVAILABLE")


class _ServiceLifecycle:
    """Workload must own quiescence; this state machine does not infer it."""

    def __init__(self, report: Callable[[int, int, int, int], None]) -> None:
        self._report = report
        self._lock = Lock()
        self.stop_event = Event()
        self.state = None
        self.ready = False
        self.checkpoint = 0
        self.report_failed = False

    def _safe_report(self, state: int, accepted: int, error: int,
                     checkpoint: int) -> None:
        try:
            self._report(state, accepted, error, checkpoint)
        except BaseException:
            self.report_failed = True
            raise

    def _transition(self, state: int, *, error: int = 0) -> None:
        with self._lock:
            if state in (START_PENDING, STOP_PENDING):
                self.checkpoint += 1
            else:
                self.checkpoint = 0
            self._safe_report(state, SERVICE_ACCEPT_STOP if state == RUNNING else 0,
                              error, self.checkpoint)
            self.state = state

    def mark_ready(self) -> None:
        with self._lock:
            if self.state != START_PENDING or self.stop_event.is_set():
                raise WindowsServiceDispatcherError()
            self._safe_report(RUNNING, SERVICE_ACCEPT_STOP, 0, 0)
            self.state = RUNNING
            self.ready = True
            self.checkpoint = 0

    def request_stop(self) -> None:
        self.stop_event.set()
        with self._lock:
            if self.state in (START_PENDING, RUNNING):
                self.checkpoint += 1
                self._safe_report(STOP_PENDING, 0, 0, self.checkpoint)
                self.state = STOP_PENDING

    def stop_pending_tick(self) -> None:
        with self._lock:
            if self.state != STOP_PENDING:
                raise WindowsServiceDispatcherError()
            self.checkpoint += 1
            self._safe_report(STOP_PENDING, 0, 0, self.checkpoint)

    def run(self, workload: Callable[[Event, Callable[[], None]], None]) -> bool:
        try:
            self._transition(START_PENDING)
            workload(self.stop_event, self.mark_ready)
            if (not self.ready or not self.stop_event.is_set()
                    or self.report_failed):
                raise WindowsServiceDispatcherError()
            self._transition(STOPPED)
            return True
        except BaseException:
            # A runner that reports success before quiescence violates its contract;
            # callers must not interpret this status alone as OS/handle clearance.
            try:
                self._transition(STOPPED, error=1)
            except BaseException:
                pass
            return False


def run_windows_service(role: str,
                        workload: Callable[[Event, Callable[[], None]], None]) -> None:
    """Connect one fixed-name own-process service to SCM; no install operation."""
    if (sys.platform != "win32" or type(role) is not str
            or role not in SERVICE_NAMES or not callable(workload)):
        raise WindowsServiceDispatcherError()

    service_main_type = ctypes.WINFUNCTYPE(None, wintypes.DWORD,
                                          ctypes.POINTER(wintypes.LPWSTR))
    handler_type = ctypes.WINFUNCTYPE(wintypes.DWORD, wintypes.DWORD,
                                     wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID)

    class ServiceTableEntry(ctypes.Structure):
        _fields_ = (("service_name", wintypes.LPWSTR),
                    ("service_main", service_main_type))

    class ServiceStatus(ctypes.Structure):
        _fields_ = (("service_type", wintypes.DWORD),
                    ("current_state", wintypes.DWORD),
                    ("controls_accepted", wintypes.DWORD),
                    ("win32_exit_code", wintypes.DWORD),
                    ("service_specific_exit_code", wintypes.DWORD),
                    ("checkpoint", wintypes.DWORD),
                    ("wait_hint", wintypes.DWORD))

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.RegisterServiceCtrlHandlerExW.argtypes = (
        wintypes.LPCWSTR, handler_type, wintypes.LPVOID)
    advapi.RegisterServiceCtrlHandlerExW.restype = wintypes.HANDLE
    advapi.SetServiceStatus.argtypes = (wintypes.HANDLE,
                                       ctypes.POINTER(ServiceStatus))
    advapi.SetServiceStatus.restype = wintypes.BOOL
    advapi.StartServiceCtrlDispatcherW.argtypes = (
        ctypes.POINTER(ServiceTableEntry),)
    advapi.StartServiceCtrlDispatcherW.restype = wintypes.BOOL

    outcome = [False]
    lifecycle = [None]
    handle = [None]

    def report(state: int, accepted: int, error: int, checkpoint: int) -> None:
        status = ServiceStatus(
            SERVICE_WIN32_OWN_PROCESS, state, accepted,
            ERROR_SERVICE_SPECIFIC_ERROR if error else 0, error,
            checkpoint, 30000 if state in (START_PENDING, STOP_PENDING) else 0)
        if not advapi.SetServiceStatus(handle[0], ctypes.byref(status)):
            raise WindowsServiceDispatcherError()

    def handler(control: int, event_type: int, event_data: object,
                context: object) -> int:
        if control == SERVICE_CONTROL_STOP and lifecycle[0] is not None:
            try:
                lifecycle[0].request_stop()
            except BaseException:
                outcome[0] = False
        return 0

    handler_callback = handler_type(handler)

    def service_main(argc: int, argv: object) -> None:
        try:
            handle[0] = advapi.RegisterServiceCtrlHandlerExW(
                SERVICE_NAMES[role], handler_callback, None)
            if not handle[0]:
                return
            lifecycle[0] = _ServiceLifecycle(report)
            outcome[0] = lifecycle[0].run(workload)
        except BaseException:
            outcome[0] = False
            if handle[0]:
                try:
                    report(STOPPED, 0, 1, 0)
                except BaseException:
                    pass

    main_callback = service_main_type(service_main)
    table = (ServiceTableEntry * 2)()
    table[0].service_name = SERVICE_NAMES[role]
    table[0].service_main = main_callback
    if not advapi.StartServiceCtrlDispatcherW(table) or not outcome[0]:
        raise WindowsServiceDispatcherError()
